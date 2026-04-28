"""Agent-agnostic routing engine - resolves workflow+task to delegate_to agent + model."""

from agent_delegator.registry import get_route, get_agent


def resolve_route(registry: dict, workflow: str, task: str, from_agent: str = "_any_agent_") -> tuple[str, str]:
    """Resolve a workflow + task combination to (agent, model).

    Falls back to first available agent with any model if no route found.
    """
    route = get_route(registry, workflow, task, from_agent)
    if route:
        return route["delegate_to"], route["preferred_model"]

    priority = registry.get("provider_priority", [])
    for agent_name in priority:
        agent_def = get_agent(registry, agent_name)
        if agent_def and agent_def.get("available_models"):
            return agent_name, agent_def["available_models"][0]["id"]

    return ("claude", "claude-sonnet-4-6")


def get_capability_match(registry: dict, capabilities: list[str]) -> str | None:
    """Find the best agent+model matching requested capabilities."""
    priority = registry.get("provider_priority", [])
    for agent_name in priority:
        agent_def = get_agent(registry, agent_name)
        if not agent_def:
            continue
        for model_def in agent_def.get("available_models", []):
            model_caps = set(model_def.get("capabilities", []))
            if all(c in model_caps for c in capabilities):
                return f"{agent_name}:{model_def['id']}"
    return None
