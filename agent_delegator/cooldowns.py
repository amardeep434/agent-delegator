"""Circuit breaker - failure tracking with exponential cooldown."""

from datetime import datetime, timezone, timedelta
from agent_delegator.state import cooldowns_path
from agent_delegator.utils import load_json, save_json


def _load_cooldowns() -> dict:
    return load_json(str(cooldowns_path()))


def _save_cooldowns(data: dict) -> None:
    save_json(str(cooldowns_path()), data)


def _key(agent: str, model: str) -> str:
    return f"{agent}:{model}"


def is_cooled_down(agent: str, model: str) -> bool:
    """Check if a provider+model is currently in cooldown."""
    data = _load_cooldowns()
    entry = data.get(_key(agent, model), {})
    cooldown_until = entry.get("cooldown_until")
    if not cooldown_until:
        return False
    try:
        until = datetime.fromisoformat(cooldown_until)
        return datetime.now(timezone.utc) < until
    except (ValueError, TypeError):
        return False


def record_failure(agent: str, model: str, registry: dict | None = None) -> None:
    """Record a failure and apply cooldown if threshold reached."""
    data = _load_cooldowns()
    key = _key(agent, model)
    entry = data.get(key, {"failure_count": 0})

    entry["failure_count"] = entry.get("failure_count", 0) + 1
    entry["last_failure"] = datetime.now(timezone.utc).isoformat()

    threshold = 3
    base_minutes = 5
    max_minutes = 60
    if registry:
        cd_config = registry.get("cooldown", {})
        threshold = cd_config.get("failure_threshold", 3)
        base_minutes = cd_config.get("base_minutes", 5)
        max_minutes = cd_config.get("max_minutes", 60)

    if entry["failure_count"] >= threshold:
        failures = entry["failure_count"]
        cooldown_mins = min(base_minutes * (2 ** (failures - threshold)), max_minutes)
        cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=cooldown_mins)
        entry["cooldown_until"] = cooldown_until.isoformat()

    data[key] = entry
    _save_cooldowns(data)


def record_success(agent: str, model: str) -> None:
    """Reset cooldown on success."""
    data = _load_cooldowns()
    key = _key(agent, model)
    if key in data:
        del data[key]
        _save_cooldowns(data)


def get_active_cooldowns() -> dict:
    """Get all currently active cooldowns."""
    data = _load_cooldowns()
    active = {}
    for key, entry in data.items():
        cooldown_until = entry.get("cooldown_until")
        if cooldown_until:
            try:
                until = datetime.fromisoformat(cooldown_until)
                if datetime.now(timezone.utc) < until:
                    active[key] = entry
            except (ValueError, TypeError):
                pass
    return active
