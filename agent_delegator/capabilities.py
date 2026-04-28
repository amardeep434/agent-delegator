"""Capability announcements and discovery for agents."""

from datetime import datetime, timezone
from agent_delegator.state import capabilities_path
from agent_delegator.utils import load_json, save_json
from agent_delegator.registry import load_registry


def announce_capabilities(agent_name: str, capabilities: list[str], models: list[str]) -> None:
    """Publish capabilities for an agent."""
    data = load_json(str(capabilities_path()))
    data[agent_name] = {
        "announced_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": capabilities,
        "models_available": models,
    }
    save_json(str(capabilities_path()), data)


def get_capabilities(agent_name: str | None = None) -> dict:
    """Get capability announcements for an agent or all agents."""
    data = load_json(str(capabilities_path()))
    if agent_name:
        return data.get(agent_name, {})
    return data


def discover_capabilities(registry: dict | None = None) -> dict:
    """Auto-discover capabilities from the registry (fallback when no announcements)."""
    if registry is None:
        registry = load_registry()
    discovered = {}
    for agent_name, agent_def in registry.get("agents", {}).items():
        models = agent_def.get("available_models", [])
        caps = set()
        for m in models:
            for c in m.get("capabilities", []):
                caps.add(c)
        discovered[agent_name] = {
            "capabilities": sorted(caps),
            "models_available": [m["id"] for m in models],
        }
    return discovered
