"""Dashboard API endpoints. All functions read from existing delegator state."""

import threading
import time
from delegator.registry import load_registry
from delegator.health import check_all_agents
from delegator.cooldowns import get_active_cooldowns
from delegator.metrics import get_recent_delegations, get_success_rate
from delegator.optimizer import get_rankings
from delegator.executor import execute
from delegator.models import DelegationRequest

_active_tasks = {}


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

    active_tasks = [{"id": tid, "agent": t.get("agent", ""), "model": t.get("model", ""),
                     "task": t.get("task", ""), "started_at": t.get("start_time", 0)}
                    for tid, t in _active_tasks.items()]

    return {
        "agents": agents,
        "active_tasks": active_tasks,
        "cooldowns": [{"key": k, **v} for k, v in cooldowns.items()],
        "success_rate": rate,
        "recent_dels": len(recent),
        "rankings": rankings,
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
    return {
        "provider_priority": registry.get("provider_priority", []),
        "cooldown_config": registry.get("cooldown", {}),
    }


def post_config(body):
    return {"status": "ok", "message": "Config updates via dashboard will be implemented in v2"}


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
        return {"status": "error", "message": result["error"]}
    r = result["data"]
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
