"""Dashboard API endpoints. All functions read from existing delegator state."""

import json
import os
import re as _re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from agent_delegator.registry import load_registry
from agent_delegator.health import check_all_agents
from agent_delegator.cooldowns import get_active_cooldowns
from agent_delegator.metrics import get_recent_delegations, get_success_rate, set_liked, get_liked, classify_failure, record_delegation
from agent_delegator.optimizer import get_rankings
from agent_delegator.executor import execute
from agent_delegator.models import DelegationRequest
from agent_delegator.utils import load_json, save_json

_active_tasks = {}
_active_outputs = {}  # task_id -> list of output lines
_scheduled_tasks = []
_pending_queue = []
_notification_config = {
    "telegram": {"bot_token": "", "chat_id": "", "events": []},
    "webhooks": {"slack_url": "", "events": []},
}
_current_project = os.getcwd()

# DoS limits
_MAX_CONCURRENT_TASKS = 10
_MAX_QUEUE_SIZE = 50
_MAX_SCHEDULED_SIZE = 20
_MAX_OUTPUT_LINES = 100
_MAX_OUTPUT_AGE_SECONDS = 3600

_SHELL_META = _re.compile(r'[;&|`$(){}[\]\\]')
_TELEGRAM_TOKEN_RE = _re.compile(r'^\d+:[A-Za-z0-9_-]+$')
_URL_RE = _re.compile(r'^https?://[^\s/$.?#].[^\s]*$', _re.IGNORECASE)


def _discover_projects():
    projects = []
    for base in [os.path.expanduser("~"), os.path.expanduser("~/projects")]:
        if not os.path.isdir(base):
            continue
        try:
            for e in os.listdir(base):
                fp = os.path.join(base, e)
                if os.path.isdir(fp) and os.path.exists(os.path.join(fp, ".agent-delegator.json")):
                    projects.append({"name": e, "path": fp})
        except PermissionError:
            pass
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, ".agent-delegator.json")) and cwd not in [p["path"] for p in projects]:
        projects.insert(0, {"name": os.path.basename(cwd), "path": cwd})
    return projects[:10]


def get_projects():
    return {"projects": _discover_projects(), "current": _current_project}


def post_project(body):
    global _current_project
    p = body.get("path", "")
    if not isinstance(p, str):
        return {"status": "error", "message": "Invalid path"}
    # Prevent path traversal and ensure it's a real directory
    resolved = os.path.realpath(p)
    if ".." in p or not os.path.isdir(resolved):
        return {"status": "error", "message": "Not found"}
    _current_project = resolved
    return {"status": "ok", "project": os.path.basename(resolved)}


_last_cleanup = {}


def _state_dir():
    p = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))) / "agent-delegator"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_notification_config():
    from agent_delegator.secrets import decrypt_config
    cfg_path = _state_dir() / "notification_config.json"
    if cfg_path.exists():
        raw = load_json(str(cfg_path))
        return decrypt_config(raw)
    return _notification_config


def _save_notification_config(cfg):
    from agent_delegator.secrets import encrypt_config
    save_json(str(_state_dir() / "notification_config.json"), encrypt_config(cfg))


def _is_internal_url(url: str) -> bool:
    """Block SSRF to internal networks and localhost."""
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return True
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return True
        # Block private IP ranges
        import ipaddress
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
                return True
        except ValueError:
            pass  # Not an IP, continue
        # Block common internal TLDs and metadata endpoints
        if hostname in ("metadata.google.internal", "169.254.169.254"):
            return True
        if hostname.endswith(".internal") or hostname.endswith(".local"):
            return True
    except Exception:
        return True
    return False


def _send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return {"ok": False, "error": "Bot token and chat ID are required"}
    if not _TELEGRAM_TOKEN_RE.match(bot_token):
        return {"ok": False, "error": "Invalid bot token format"}
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        if _is_internal_url(url):
            return {"ok": False, "error": "Invalid URL"}
        # Escape HTML in message to prevent injection in Telegram
        safe_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        data = json.dumps({"chat_id": chat_id, "text": safe_msg[:4000], "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=5)
        body = json.loads(resp.read().decode())
        if body.get("ok"):
            return {"ok": True}
        return {"ok": False, "error": body.get("description", "Unknown Telegram error")}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            return {"ok": False, "error": body.get("description", f"HTTP {e.code}")}
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": "Request failed"}


def _send_slack(webhook_url, message):
    if not webhook_url:
        return {"ok": False, "error": "Webhook URL is required"}
    if not _URL_RE.match(webhook_url):
        return {"ok": False, "error": "Invalid URL format"}
    if _is_internal_url(webhook_url):
        return {"ok": False, "error": "Invalid URL"}
    try:
        data = json.dumps({"text": message[:4000]}).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return {"ok": True}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": "Request failed"}


def _dispatch_notification(event_type, event_data):
    cfg = _load_notification_config()
    tg = cfg.get("telegram", {})
    wh = cfg.get("webhooks", {})

    # Build message with HTML-escaped values
    def _esc(val):
        if not isinstance(val, str):
            val = str(val)
        return val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if event_type == "task_completed":
        msg = f"✅ <b>Task Completed</b>\nID: {_esc(event_data.get('task_id',''))}\nProvider: {_esc(event_data.get('provider',''))}\nDuration: {_esc(event_data.get('duration',''))}"
    elif event_type == "task_failed":
        msg = f"❌ <b>Task Failed</b>\nID: {_esc(event_data.get('task_id',''))}\nError: {_esc(event_data.get('error',''))}"
    elif event_type == "rate_limit":
        msg = f"⚠ <b>Rate Limit Detected</b>\nProvider: {_esc(event_data.get('provider',''))}\nFallback count: {_esc(event_data.get('fallback_count','0'))}"
    else:
        msg = _esc(event_data.get("message", str(event_data)))

    if event_type in tg.get("events", []):
        _send_telegram(tg.get("bot_token", ""), tg.get("chat_id", ""), msg)
    if event_type in wh.get("events", []):
        _send_slack(wh.get("slack_url", ""), msg)


def get_agent_models(agent_name):
    """Get per-model stats for an agent."""
    registry = load_registry(project_root=_current_project)
    agent_def = registry.get("agents", {}).get(agent_name)
    if not agent_def:
        return {"error": "Agent not found"}
    recent = get_recent_delegations(100)
    models = []
    for m in agent_def.get("available_models", []):
        mid = m.get("id", "")
        model_dels = [d for d in recent if d.get("provider_used") == agent_name or d.get("to_agent") == agent_name]
        total = len(model_dels)
        ok = sum(1 for d in model_dels if d.get("success"))
        models.append({
            "id": mid,
            "display": m.get("display", mid),
            "capabilities": m.get("capabilities", []),
            "total_dels": total,
            "success_dels": ok,
            "success_rate": round(ok / total, 2) if total > 0 else 1.0,
        })
    return {"agent": agent_name, "models": models}


def get_status():
    _cleanup_stale_tasks()
    registry = load_registry(project_root=_current_project)
    health = check_all_agents(registry)
    cooldowns = get_active_cooldowns()
    recent = get_recent_delegations(20)
    rate = get_success_rate(days=7)
    rankings = get_rankings()

    agents = []
    for name, agent_def in registry.get("agents", {}).items():
        h = health.get(name, {})
        agent_rate = get_success_rate(agent=name, days=7)
        agent_dels = sum(1 for d in recent if d.get("to_agent") == name or d.get("provider_used") == name)
        agents.append({
            "name": name,
            "available": h.get("available", False),
            "current_model": agent_def.get("available_models", [{}])[0].get("id", ""),
            "model_count": len(agent_def.get("available_models", [])),
            "models": [m.get("id", "") for m in agent_def.get("available_models", [])],
            "success_rate": agent_rate,
            "del_count": agent_dels,
            "est_cost": round(agent_dels * 0.005, 2),
        })

    active = [
        {"id": tid, "agent": t.get("agent", ""), "model": t.get("model", ""),
         "task": t.get("task", ""), "started_at": t.get("start_time", 0)}
        for tid, t in _active_tasks.items()
    ]

    import time as _time
    cooldown_list = []
    for k, v in cooldowns.items():
        until = v.get("cooldown_until", 0)
        remaining = max(0, int(until - _time.time())) if until else 0
        cooldown_list.append({"key": k, "remaining_seconds": remaining, **v})

    return {
        "agents": agents,
        "active_tasks": active,
        "cooldowns": cooldown_list,
        "success_rate": rate,
        "recent_dels": len(recent),
        "rankings": rankings,
        "pending_queue": len(_pending_queue),
        "scheduled": len(_scheduled_tasks),
        "project": os.path.basename(_current_project),
    }


def get_metrics(agent=None, days=7):
    rate = get_success_rate(agent=agent, days=days)
    recent = get_recent_delegations(limit=200)
    if agent:
        recent = [d for d in recent if d.get("to_agent") == agent or d.get("provider_used") == agent]

    costs = {}
    for d in recent:
        ag = d.get("to_agent", d.get("provider_used", "unknown"))
        costs[ag] = costs.get(ag, 0) + float(d.get("cost") or 0)

    failures = {}
    for d in recent:
        if not d.get("success"):
            ft = d.get("failure_type", "unknown")
            failures[ft] = failures.get(ft, 0) + 1

    rankings = []
    by_agent = {}
    for d in recent:
        ag = d.get("to_agent", d.get("provider_used", "unknown"))
        if ag not in by_agent:
            by_agent[ag] = {"total": 0, "ok": 0}
        by_agent[ag]["total"] += 1
        if d.get("success"):
            by_agent[ag]["ok"] += 1

    for ag, stats in sorted(by_agent.items(), key=lambda x: (x[1]["ok"] / x[1]["total"] if x[1]["total"] else 0), reverse=True):
        sr = stats["ok"] / stats["total"] if stats["total"] else 1.0
        rankings.append({"agent": ag, "score": round(sr, 2), "dels": stats["total"]})

    return {
        "success_rate": rate,
        "delegations": recent,
        "total": len(recent),
        "costs": costs,
        "failures": failures,
        "rankings": rankings,
    }


def get_logs(agent=None, level=None, limit=200):
    recent = get_recent_delegations(limit=min(limit, 500))
    entries = []
    for d in recent:
        msg = f"Task {d.get('id', '')}: {d.get('workflow', '')}/{d.get('task_type', '')}"
        lvl = "ERROR" if not d.get("success") else "INFO"
        entries.append({
            "timestamp": d.get("timestamp", ""),
            "agent": d.get("to_agent", d.get("provider_used", "")),
            "task_id": d.get("id", ""),
            "level": lvl,
            "message": msg,
        })
    # Aggregation data
    by_level = {"ERROR": 0, "WARN": 0, "INFO": 0, "DEBUG": 0}
    by_agent = {}
    top_errors = {}
    for d in recent:
        lvl = "ERROR" if not d.get("success") else "INFO"
        by_level[lvl] = by_level.get(lvl, 0) + 1
        ag = d.get("to_agent", d.get("provider_used", "unknown"))
        by_agent[ag] = by_agent.get(ag, 0) + 1
        if not d.get("success"):
            ft = d.get("failure_type", "unknown")
            top_errors[ft] = top_errors.get(ft, 0) + 1

    error_rate = by_level["ERROR"] / len(recent) if recent else 0
    top_errors_list = [{"type": k, "count": v} for k, v in sorted(top_errors.items(), key=lambda x: -x[1])[:5]]

    return {
        "entries": entries,
        "total": len(entries),
        "by_level": by_level,
        "by_agent": by_agent,
        "top_errors": top_errors_list,
        "error_rate": round(error_rate, 4),
        "avg_response_time": round(sum(d.get("duration_ms", 0) for d in recent) / len(recent) / 1000, 1) if recent else 0,
        "active_sessions": len(set(d.get("to_agent", "") for d in recent)),
        "log_rate": round(len(recent) / 7, 1),
    }


def get_routes():
    registry = load_registry(project_root=_current_project, force_reload=True)
    routes = []
    matrix = registry.get("routing_matrix", {}).get("_any_agent_", {})
    for workflow, tasks in matrix.items():
        for task, route in tasks.items():
            routes.append({
                "workflow": workflow,
                "task": task,
                "agent": route["delegate_to"],
                "model": route["preferred_model"],
            })
    return {"routes": routes}


def get_config():
    registry = load_registry(project_root=_current_project, force_reload=True)
    cfg = _load_notification_config()
    return {
        "provider_priority": registry.get("provider_priority", []),
        "cooldown_config": registry.get("cooldown", {}),
        "notifications": cfg,
        "preferences": cfg.get("preferences", {}),
        "pending_queue": [{"task": q.get("task"), "model": q.get("model"), "workflow": q.get("workflow")} for q in _pending_queue],
        "scheduled": [{"task": s.get("task"), "model": s.get("model"), "workflow": s.get("workflow"), "cron": s.get("cron", "")} for s in _scheduled_tasks],
    }


def _validate_task(task: str) -> tuple:
    """Validate task description. Returns (ok, error_message)."""
    if not task or not isinstance(task, str):
        return False, "Task description required"
    if len(task) > 5000:
        return False, "Task too long (max 5000 chars)"
    if _SHELL_META.search(task):
        return False, "Task contains invalid characters"
    return True, ""


def post_config(body):
    key = body.get("key", "")
    if not isinstance(key, str):
        return {"status": "error", "message": "Invalid key"}

    if key == "notifications":
        _save_notification_config(body.get("notifications", _notification_config))
        return {"status": "ok", "message": "Notification config persisted"}
    if key == "auto_heal":
        # Reset all cooldowns by clearing the cooldowns file
        from agent_delegator.state import cooldowns_path
        save_json(str(cooldowns_path()), {})
        return {"status": "ok", "message": "All cooldowns reset"}
    if key == "clear_history":
        from agent_delegator.metrics import clear_delegations
        clear_delegations()
        return {"status": "ok", "message": "History cleared"}
    if key == "test_telegram":
        token = body.get("token", "")
        chat_id = body.get("chat_id", "")
        if not _TELEGRAM_TOKEN_RE.match(token):
            return {"status": "error", "message": "Invalid bot token format"}
        if not isinstance(chat_id, str) or not chat_id:
            return {"status": "error", "message": "Chat ID required"}
        result = _send_telegram(token, chat_id, "🧪 Test message from delegator dashboard")
        if result.get("ok"):
            return {"status": "ok", "message": "Telegram test sent"}
        return {"status": "error", "message": f"Telegram failed: {result.get('error', 'unknown')}"}
    if key == "test_webhook":
        url = body.get("url", "")
        if not _URL_RE.match(url):
            return {"status": "error", "message": "Invalid URL format"}
        if _is_internal_url(url):
            return {"status": "error", "message": "Invalid URL"}
        result = _send_slack(url, "🧪 Test message from delegator dashboard")
        if result.get("ok"):
            return {"status": "ok", "message": "Webhook test sent"}
        return {"status": "error", "message": f"Webhook failed: {result.get('error', 'unknown')}"}
    if key == "cooldown":
        user_cfg = body.get("config", {})
        if not isinstance(user_cfg, dict):
            return {"status": "error", "message": "Invalid config"}
        project_cfg = Path(_current_project) / ".agent-delegator.json"
        if project_cfg.exists():
            cfg = load_json(str(project_cfg))
            cfg["cooldown"] = user_cfg
            save_json(str(project_cfg), cfg)
        else:
            import agent_delegator.registry
            reg = load_registry(project_root=_current_project)
            reg["cooldown"] = user_cfg
            from agent_delegator.registry import save_registry
            save_registry(reg)
            delegator.registry._cached_registry = None
        return {"status": "ok", "message": "Circuit breaker config saved"}
    if key == "preferences":
        cfg = _load_notification_config()
        prefs = body.get("prefs", {})
        if not isinstance(prefs, dict):
            return {"status": "error", "message": "Invalid preferences"}
        cfg["preferences"] = prefs
        _save_notification_config(cfg)
        return {"status": "ok", "message": "Preferences saved"}
    if key == "add_scheduled":
        if len(_scheduled_tasks) >= _MAX_SCHEDULED_SIZE:
            return {"status": "error", "message": f"Max {_MAX_SCHEDULED_SIZE} scheduled tasks"}
        task = body.get("task", "")
        ok, err = _validate_task(task)
        if not ok:
            return {"status": "error", "message": err}
        _scheduled_tasks.append({
            "task": task,
            "model": body.get("model", "federated-coding"),
            "workflow": body.get("workflow", "subagent-driven"),
            "cron": body.get("cron", ""),
        })
        return {"status": "ok", "message": "Scheduled task added"}
    if key == "add_pending":
        if len(_pending_queue) >= _MAX_QUEUE_SIZE:
            return {"status": "error", "message": f"Max {_MAX_QUEUE_SIZE} pending tasks"}
        task = body.get("task", "")
        ok, err = _validate_task(task)
        if not ok:
            return {"status": "error", "message": err}
        _pending_queue.append({
            "task": task,
            "model": body.get("model", "federated-coding"),
            "workflow": body.get("workflow", "subagent-driven"),
        })
        return {"status": "ok", "message": "Task queued"}
    if key == "start_queued":
        idx = body.get("index", 0)
        if not isinstance(idx, int) or not (0 <= idx < len(_pending_queue)):
            return {"status": "error", "message": "Invalid queue index"}
        q = _pending_queue.pop(idx)
        req = DelegationRequest(task=q["task"], model=q["model"], workflow=q["workflow"], no_worktree=True)
        t = threading.Thread(target=lambda: execute(req), daemon=True)
        t.start()
        return {"status": "ok", "message": f"Started: {q['task']}"}
    if key == "reset_rankings":
        from agent_delegator.state import rankings_path
        save_json(str(rankings_path()), {})
        return {"status": "ok", "message": "Rankings reset"}
    if key == "like_delegation":
        set_liked(body.get("delegation_id", ""), body.get("liked", False))
        return {"status": "ok", "message": "Like updated"}
    if key == "routing_priority":
        import agent_delegator.registry
        from agent_delegator.registry import save_registry, load_registry
        pri = body.get("priority", [])
        if not isinstance(pri, list):
            return {"status": "error", "message": "Invalid priority"}
        project_cfg = Path(_current_project) / ".agent-delegator.json"
        if project_cfg.exists():
            cfg = load_json(str(project_cfg))
            cfg["provider_priority"] = pri
            save_json(str(project_cfg), cfg)
        else:
            reg = load_registry(project_root=_current_project)
            reg["provider_priority"] = pri
            save_registry(reg)
        delegator.registry._cached_registry = None
        return {"status": "ok", "message": "Routing priority saved"}
    if key == "add_route":
        import agent_delegator.registry
        from agent_delegator.registry import save_registry, load_registry
        reg = load_registry(project_root=_current_project)
        matrix = reg.setdefault("routing_matrix", {}).setdefault("_any_agent_", {})
        wf = body.get("workflow", "subagent-driven")
        task = body.get("task", "implementation")
        matrix.setdefault(wf, {})[task] = {
            "delegate_to": body.get("agent", "opencode"),
            "preferred_model": body.get("model", "federated-coding"),
        }
        project_cfg = Path(_current_project) / ".agent-delegator.json"
        if project_cfg.exists():
            cfg = load_json(str(project_cfg))
            cfg.setdefault("routing_matrix", {}).setdefault("_any_agent_", {}).setdefault(wf, {})[task] = {
                "delegate_to": body.get("agent", "opencode"),
                "preferred_model": body.get("model", "federated-coding"),
            }
            save_json(str(project_cfg), cfg)
        else:
            save_registry(reg)
        delegator.registry._cached_registry = None
        return {"status": "ok", "message": "Route added"}
    if key == "remove_route":
        import agent_delegator.registry
        from agent_delegator.registry import save_registry, load_registry
        reg = load_registry(project_root=_current_project)
        matrix = reg.get("routing_matrix", {}).get("_any_agent_", {})
        wf = body.get("workflow", "")
        task = body.get("task", "")
        if wf in matrix and task in matrix[wf]:
            del matrix[wf][task]
            project_cfg = Path(_current_project) / ".agent-delegator.json"
            if project_cfg.exists():
                cfg = load_json(str(project_cfg))
                proj_matrix = cfg.get("routing_matrix", {}).get("_any_agent_", {})
                if wf in proj_matrix and task in proj_matrix[wf]:
                    del proj_matrix[wf][task]
                    save_json(str(project_cfg), cfg)
            else:
                save_registry(reg)
            delegator.registry._cached_registry = None
        return {"status": "ok", "message": "Route removed"}
    return {"status": "ok", "message": "Config saved"}


def post_compare(body):
    task = body.get("task", "")
    ok, err = _validate_task(task)
    if not ok:
        return {"status": "error", "message": err}
    model_a = body.get("model_a", "opencode-go/deepseek-v4-pro")
    model_b = body.get("model_b", "claude-sonnet-4-6")
    if len(_active_tasks) >= _MAX_CONCURRENT_TASKS:
        return {"status": "error", "message": "Too many concurrent tasks"}
    results = {}
    for label, m in [("A", model_a), ("B", model_b)]:
        req = DelegationRequest(task=task, model=m, workflow="subagent-driven", no_worktree=True)
        result = {"data": None, "error": None}
        def _run():
            try:
                result["data"] = execute(req)
            except Exception as e:
                result["error"] = str(e)[:200]
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=30)
        if t.is_alive():
            results[label] = {"model": m, "error": "timeout (30s)", "success": False}
        elif result["error"]:
            results[label] = {"model": m, "error": result["error"], "success": False}
        else:
            r = result["data"]
            results[label] = {
                "model": m,
                "success": r.success,
                "provider": r.provider_used,
                "duration_ms": r.duration_ms,
                "fallback_count": r.fallback_count,
                "output": r.output[:2000] if r.output else "",
            }
    return {"status": "ok", "results": results}


def post_exec(body):
    _cleanup_stale_tasks()
    task = body.get("task", "")
    model = body.get("model", "federated-coding")
    workflow = body.get("workflow", "subagent-driven")
    from_agent = body.get("from_agent", "")
    stream = body.get("stream", True)
    no_worktree = body.get("no_worktree", True)

    ok, err = _validate_task(task)
    if not ok:
        return {"status": "error", "message": err}

    if len(_active_tasks) >= _MAX_CONCURRENT_TASKS:
        return {"status": "error", "message": "Too many concurrent tasks"}

    request = DelegationRequest(
        task=task, model=model, workflow=workflow, from_agent=from_agent,
        stream=stream, no_worktree=no_worktree,
    )

    result = {"data": None, "error": None}

    def _run():
        try:
            result["data"] = execute(request)
        except Exception as e:
            result["error"] = "Execution failed"

    _active_tasks[request.id] = {"agent": from_agent or "", "model": model, "task": task, "start_time": time.time()}
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5)
    if t.is_alive():
        return {"status": "running", "task_id": request.id}

    # Task finished within timeout — remove from active list
    _active_tasks.pop(request.id, None)

    if result["error"]:
        _dispatch_notification("task_failed", {"task_id": request.id, "error": result["error"]})
        return {"status": "error", "message": result["error"]}
    r = result["data"]

    # Capture output for live view
    if r.output:
        lines = r.output.split("\n")
        _active_outputs[request.id] = lines[-_MAX_OUTPUT_LINES:]
        _cleanup_old_outputs()

    if r.success:
        _dispatch_notification("task_completed", {"task_id": request.id, "provider": r.provider_used, "duration": f"{r.duration_ms}ms"})
    else:
        _dispatch_notification("task_failed", {"task_id": request.id, "error": r.error or "unknown"})

    cost = round((r.duration_ms or 0) * 0.000001, 4)
    failure_type = classify_failure(r.success, r.fallback_count, r.error or "")
    record_delegation(
        request_id=request.id,
        from_agent=from_agent,
        to_agent=r.provider_used or "",
        model=r.model_used or model,
        provider_used=r.provider_used or "",
        workflow=workflow,
        task_type=task[:50],
        success=r.success,
        fallback_count=r.fallback_count,
        duration_ms=r.duration_ms or 0,
        cost=cost,
        failure_type=failure_type,
    )

    return {
        "status": "success" if r.success else "failed",
        "task_id": request.id,
        "provider_used": r.provider_used,
        "model_used": r.model_used,
        "fallback_count": r.fallback_count,
        "duration_ms": r.duration_ms,
        "output": r.output[:5000] if r.output else "",
        "error": r.error,
    }


def _cleanup_old_outputs():
    """Remove old outputs to prevent memory exhaustion."""
    now = time.time()
    to_remove = []
    for tid, lines in list(_active_outputs.items()):
        # Heuristic: if task not in active and we have no timestamp, use a simple count limit
        if tid not in _active_tasks and len(_active_outputs) > _MAX_CONCURRENT_TASKS * 2:
            to_remove.append(tid)
    for tid in to_remove:
        _active_outputs.pop(tid, None)


def _cleanup_stale_tasks():
    """Remove tasks that have been running for too long to prevent memory leaks."""
    now = time.time()
    stale_threshold = 3600  # 1 hour
    to_remove = []
    for tid, task in list(_active_tasks.items()):
        start = task.get("start_time", 0)
        if start and (now - start) > stale_threshold:
            to_remove.append(tid)
    for tid in to_remove:
        _active_tasks.pop(tid, None)
        _active_outputs.pop(tid, None)


def exec_from_queue(task, model):
    req = DelegationRequest(task=task, model=model or "federated-coding", workflow="subagent-driven", no_worktree=True)
    result = execute(req)
    if result.output:
        lines = result.output.split("\n")
        _active_outputs[req.id] = lines[-_MAX_OUTPUT_LINES:]
    return {"status": "ok", "task_id": req.id, "provider": result.provider_used, "output": (result.output or "")[:2000]}


def post_stop_task(task_id):
    if task_id in _active_tasks:
        del _active_tasks[task_id]
        _active_outputs.pop(task_id, None)
        return {"status": "ok", "message": f"Task {task_id} stopped"}
    return {"status": "error", "message": "Task not found"}


def get_task_output(task_id):
    _cleanup_stale_tasks()
    if task_id in _active_tasks:
        return {"task_id": task_id, "status": "running", "output": "\n".join(_active_outputs.get(task_id, [])[-_MAX_OUTPUT_LINES:])}
    recent = get_recent_delegations(20)
    for d in recent:
        if d.get("id") == task_id:
            return {"task_id": task_id, "status": "done", "output": f"Provider: {d.get('provider_used', '')}\nDuration: {d.get('duration_ms', 0)}ms\nFallbacks: {d.get('fallback_count', 0)}\nSuccess: {d.get('success')}"}
    return {"status": "error", "message": "Task not found"}
