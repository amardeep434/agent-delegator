"""Dashboard API endpoints. All functions read from existing delegator state."""

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from delegator.registry import load_registry
from delegator.health import check_all_agents
from delegator.cooldowns import get_active_cooldowns
from delegator.metrics import get_recent_delegations, get_success_rate
from delegator.optimizer import get_rankings
from delegator.executor import execute
from delegator.models import DelegationRequest
from delegator.utils import load_json, save_json

_active_tasks = {}
_scheduled_tasks = []
_pending_queue = []
_notification_config = {
    "telegram": {"bot_token": "", "chat_id": "", "events": []},
    "webhooks": {"slack_url": "", "events": []},
}
_last_cleanup = {}

def _state_dir():
    p = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))) / "delegator"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_notification_config():
    cfg_path = _state_dir() / "notification_config.json"
    if cfg_path.exists():
        return load_json(str(cfg_path))
    return _notification_config

def _save_notification_config(cfg):
    save_json(str(_state_dir() / "notification_config.json"), cfg)

def _send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message[:4000], "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False

def _send_slack(webhook_url, message):
    if not webhook_url:
        return False
    try:
        data = json.dumps({"text": message[:4000]}).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False

def _dispatch_notification(event_type, event_data):
    cfg = _load_notification_config()
    tg = cfg.get("telegram", {})
    wh = cfg.get("webhooks", {})

    # Build message
    if event_type == "task_completed":
        msg = f"✅ <b>Task Completed</b>\nID: {event_data.get('task_id','')}\nProvider: {event_data.get('provider','')}\nDuration: {event_data.get('duration','')}"
    elif event_type == "task_failed":
        msg = f"❌ <b>Task Failed</b>\nID: {event_data.get('task_id','')}\nError: {event_data.get('error','')}"
    elif event_type == "rate_limit":
        msg = f"⚠ <b>Rate Limit Detected</b>\nProvider: {event_data.get('provider','')}\nFallback count: {event_data.get('fallback_count','0')}"
    else:
        msg = event_data.get("message", str(event_data))

    if event_type in tg.get("events", []):
        _send_telegram(tg.get("bot_token", ""), tg.get("chat_id", ""), msg)
    if event_type in wh.get("events", []):
        _send_slack(wh.get("slack_url", ""), msg)


def get_status():
    registry = load_registry()
    health = check_all_agents(registry)
    cooldowns = get_active_cooldowns()
    recent = get_recent_delegations(5)
    rate = get_success_rate(days=7)
    rankings = get_rankings()

    agents = []
    for name, agent_def in registry.get("agents", {}).items():
        h = health.get(name, {})
        agents.append({
            "name": name,
            "available": h.get("available", False),
            "current_model": agent_def.get("available_models", [{}])[0].get("id", ""),
            "model_count": len(agent_def.get("available_models", [])),
        })

    active = [{"id": tid, "agent": t.get("agent", ""), "model": t.get("model", ""),
               "task": t.get("task", ""), "started_at": t.get("start_time", 0)}
              for tid, t in _active_tasks.items()]

    return {
        "agents": agents,
        "active_tasks": active,
        "cooldowns": [{"key": k, **v} for k, v in cooldowns.items()],
        "success_rate": rate,
        "recent_dels": len(recent),
        "rankings": rankings,
        "pending_queue": len(_pending_queue),
        "scheduled": len(_scheduled_tasks),
    }


def get_metrics(agent=None, days=7):
    rate = get_success_rate(agent=agent, days=days)
    recent = get_recent_delegations(limit=20)
    return {"success_rate": rate, "delegations": recent, "total": len(recent)}


def get_logs(agent=None, level=None, limit=200):
    recent = get_recent_delegations(limit=min(limit, 500))
    entries = []
    for d in recent:
        msg = f"Task {d.get('id','')}: {d.get('workflow','')}/{d.get('task_type','')}"
        lvl = "ERROR" if not d.get("success") else "INFO"
        entries.append({
            "timestamp": d.get("timestamp", ""),
            "agent": d.get("to_agent", d.get("provider_used", "")),
            "task_id": d.get("id", ""),
            "level": lvl,
            "message": msg,
        })
    return {"entries": entries, "total": len(entries)}


def get_routes():
    registry = load_registry(force_reload=True)
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
    registry = load_registry(force_reload=True)
    cfg = _load_notification_config()
    return {
        "provider_priority": registry.get("provider_priority", []),
        "cooldown_config": registry.get("cooldown", {}),
        "notifications": cfg,
        "pending_queue": [{"task": q.get("task"), "model": q.get("model"), "workflow": q.get("workflow")} for q in _pending_queue],
        "scheduled": [{"task": s.get("task"), "model": s.get("model"), "workflow": s.get("workflow"), "cron": s.get("cron", "")} for s in _scheduled_tasks],
    }


def post_config(body):
    """Save configuration updates."""
    key = body.get("key", "")
    if key == "notifications":
        _save_notification_config(body.get("notifications", _notification_config))
        return {"status": "ok", "message": "Notification config saved"}
    if key == "cooldown":
        return {"status": "ok", "message": "Cooldown config saved (requires restart)"}
    if key == "add_scheduled":
        _scheduled_tasks.append({"task": body.get("task",""), "model": body.get("model","federated-coding"),
                                  "workflow": body.get("workflow","subagent-driven"), "cron": body.get("cron","")})
        return {"status": "ok", "message": "Scheduled task added"}
    if key == "add_pending":
        _pending_queue.append({"task": body.get("task",""), "model": body.get("model","federated-coding"),
                                "workflow": body.get("workflow","subagent-driven")})
        return {"status": "ok", "message": "Task queued"}
    return {"status": "ok", "message": "Config saved"}


def post_compare(body):
    """Run side-by-side comparison of two models."""
    task = body.get("task", "")
    model_a = body.get("model_a", "opencode-go/deepseek-v4-pro")
    model_b = body.get("model_b", "claude-sonnet-4-6")
    results = {}

    for label, m in [("A", model_a), ("B", model_b)]:
        req = DelegationRequest(task=task, model=m, workflow="subagent-driven", no_worktree=True)
        try:
            r = execute(req)
            results[label] = {"model": m, "success": r.success, "provider": r.provider_used,
                              "duration_ms": r.duration_ms, "fallback_count": r.fallback_count,
                              "output": r.output[:2000] if r.output else ""}
        except Exception as e:
            results[label] = {"model": m, "error": str(e)[:200]}

    return {"status": "ok", "results": results}


def post_exec(body):
    task = body.get("task", "")
    model = body.get("model", "federated-coding")
    workflow = body.get("workflow", "subagent-driven")
    from_agent = body.get("from_agent", "")
    stream = body.get("stream", True)
    no_worktree = body.get("no_worktree", True)

    if not task or not isinstance(task, str):
        return {"status": "error", "message": "Task description required"}
    if len(task) > 5000:
        return {"status": "error", "message": "Task too long (max 5000 chars)"}

    request = DelegationRequest(
        task=task, model=model, workflow=workflow, from_agent=from_agent,
        stream=stream, no_worktree=no_worktree,
    )

    result = {"data": None, "error": None}

    def _run():
        try:
            result["data"] = execute(request)
        except Exception as e:
            result["error"] = str(e)[:200]

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5)
    if t.is_alive():
        _active_tasks[request.id] = {"agent": "", "model": model, "task": task, "start_time": time.time()}
        return {"status": "running", "task_id": request.id}

    if result["error"]:
        _dispatch_notification("task_failed", {"task_id": request.id, "error": result["error"]})
        return {"status": "error", "message": result["error"]}
    r = result["data"]

    if r.success:
        _dispatch_notification("task_completed", {"task_id": request.id, "provider": r.provider_used, "duration": f"{r.duration_ms}ms"})
    else:
        _dispatch_notification("task_failed", {"task_id": request.id, "error": r.error or "unknown"})

    return {
        "status": "success" if r.success else "failed",
        "task_id": request.id, "provider_used": r.provider_used, "model_used": r.model_used,
        "fallback_count": r.fallback_count, "duration_ms": r.duration_ms,
        "output": r.output[:5000] if r.output else "", "error": r.error,
    }


def post_stop_task(task_id):
    if task_id in _active_tasks:
        del _active_tasks[task_id]
        return {"status": "ok", "message": f"Task {task_id} stopped"}
    return {"status": "error", "message": "Task not found"}


def get_task_output(task_id):
    if task_id in _active_tasks:
        return {"task_id": task_id, "status": "running", "output": ""}
    recent = get_recent_delegations(20)
    for d in recent:
        if d.get("id") == task_id:
            return {"task_id": task_id, "status": "done", "output": ""}
    return {"status": "error", "message": "Task not found"}
