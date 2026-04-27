"""Registry loader - loads default registry, merges project override and env."""

import os
from pathlib import Path
from delegator.utils import load_json, deep_merge

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_REGISTRY = _SCRIPT_DIR / "registry.json"

_cached_registry: dict | None = None


def load_registry(project_root: str | None = None, force_reload: bool = False) -> dict:
    """Load the merged registry (default + project override + env overrides)."""
    global _cached_registry
    if _cached_registry is not None and not force_reload:
        return _cached_registry

    registry = load_json(str(_DEFAULT_REGISTRY))

    if project_root:
        project_config = Path(project_root) / ".delegator.json"
        if project_config.exists():
            override = load_json(str(project_config))
            registry = deep_merge(registry, override)

    env_priority = os.environ.get("DELEGATOR_PROVIDER_PRIORITY", "")
    if env_priority:
        registry["provider_priority"] = [p.strip() for p in env_priority.split(",")]

    _cached_registry = registry
    return registry


def get_agent(registry: dict, agent_name: str) -> dict | None:
    return registry.get("agents", {}).get(agent_name)


def get_logical_model(registry: dict, model_name: str) -> dict | None:
    return registry.get("logical_models", {}).get(model_name)


def get_route(registry: dict, workflow: str, task: str, from_agent: str = "_any_agent_") -> dict | None:
    """Look up a route in the routing matrix."""
    matrix = registry.get("routing_matrix", {})
    route = matrix.get(from_agent, {}).get(workflow, {}).get(task)
    if route:
        return route
    return matrix.get("_any_agent_", {}).get(workflow, {}).get(task)
