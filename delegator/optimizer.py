"""Learned routing - uses success rates to auto-tune provider priorities."""

from datetime import datetime, timezone
from delegator.metrics import get_success_rate, get_recent_delegations
from delegator.state import rankings_path
from delegator.utils import load_json, save_json


def optimize_rankings() -> dict:
    """Analyze success rates and produce optimized provider rankings."""
    recent = get_recent_delegations(limit=100)
    by_agent = {}
    for d in recent:
        agent = d.get("to_agent", "unknown")
        if agent not in by_agent:
            by_agent[agent] = {"total": 0, "success": 0}
        by_agent[agent]["total"] += 1
        if d.get("success"):
            by_agent[agent]["success"] += 1

    scored = []
    for agent, stats in by_agent.items():
        score = stats["success"] / stats["total"] if stats["total"] > 0 else 0.0
        scored.append({"agent": agent, "score": round(score, 3), "total": stats["total"]})

    scored.sort(key=lambda x: x["score"], reverse=True)

    rankings = {}
    for entry in scored:
        rankings[entry["agent"]] = {
            "score": entry["score"],
            "total_delegations": entry["total"],
        }

    result = {
        "last_optimized": datetime.now(timezone.utc).isoformat(),
        "rankings": rankings,
        "recommended_priority": [s["agent"] for s in scored],
    }

    save_json(str(rankings_path()), result)
    return result


def get_rankings() -> dict:
    """Get current learned rankings."""
    return load_json(str(rankings_path()))
