"""Model name resolver - normalizes model names per agent and resolves logical models to concrete providers."""

import shlex
from agent_delegator.registry import get_agent, get_logical_model


def normalize_model(model: str, agent: str, registry: dict) -> str:
    """Normalize a model name for use with a specific agent CLI."""
    agent_def = get_agent(registry, agent)
    if not agent_def:
        return model

    models = agent_def.get("available_models", [])
    model_ids = {m["id"] for m in models}

    if model in model_ids:
        return model

    shorthand_map = {
        "sonnet": {"claude": "claude-sonnet-4-6"},
        "haiku": {"claude": "claude-haiku-4-5"},
        "sonnet-4-6": {"claude": "claude-sonnet-4-6"},
        "haiku-4-5": {"claude": "claude-haiku-4-5"},
        "minimax": {"opencode": "opencode-go/minimax-m2.7"},
        "deepseek": {"opencode": "opencode-go/deepseek-v4-pro"},
        "deepseek-flash": {"opencode": "opencode-go/deepseek-v4-flash"},
        "kimi": {"opencode": "opencode-go/kimi-k2.6"},
        "qwen": {"opencode": "opencode-go/qwen3.6-plus"},
    }

    lower = model.lower()
    if lower in shorthand_map and agent in shorthand_map[lower]:
        return shorthand_map[lower][agent]

    return model


def resolve_logical_model(registry: dict, model_name: str, exclude_providers: list[str] | None = None) -> list[str]:
    """Resolve a logical model name into a list of concrete provider keys (agent:model)."""
    logical = get_logical_model(registry, model_name)
    if logical:
        providers = logical.get("providers", [])
        if exclude_providers:
            providers = [p for p in providers if p not in exclude_providers]
        return providers
    return []


def resolve_model(registry: dict, model_name: str, agent: str) -> str:
    """Resolve a model name to its full form for a given agent.

    1. Logical model (federated-*) -> first available provider for this agent
    2. Shorthand (sonnet) -> full ID for this agent
    3. Full ID -> pass through
    """
    logical = get_logical_model(registry, model_name)
    if logical:
        for provider in logical.get("providers", []):
            parts = provider.split(":", 1)
            if len(parts) == 2 and parts[0] == agent:
                return parts[1]
        return model_name

    return normalize_model(model_name, agent, registry)


def build_cli_command(registry: dict, agent: str, model: str, task: str, worktree: str) -> str:
    """Build the full CLI command for executing a task via a specific agent.
    
    All user-controlled values are shell-escaped to prevent command injection.
    """
    agent_def = get_agent(registry, agent)
    if not agent_def:
        raise ValueError(f"Unknown agent: {agent}")

    template = agent_def["cli_template"]
    resolved = resolve_model(registry, model, agent)
    return template.format(
        model=shlex.quote(resolved),
        task=shlex.quote(task),
        worktree=shlex.quote(worktree),
    )
