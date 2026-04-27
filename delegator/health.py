"""Proactive health checks for agent availability."""

import shutil
import subprocess
from delegator.registry import load_registry
from delegator.capabilities import announce_capabilities


def _find_cli_binary(cli_template: str, agent_name: str) -> str | None:
    """Extract the CLI binary name from the agent's template.
    
    Handles templates with && pipelines (cd ... && binary ...)
    and shell pipes (echo ... | binary ...).
    Falls back to agent_name if parsing fails.
    """
    if not cli_template:
        return agent_name
    # Split on && and | separators, look for known binary names
    segments = cli_template.replace("&&", "|").split("|")
    for seg in reversed(segments):  # check later segments first (usually has the binary)
        words = seg.strip().split()
        for word in words:
            # Skip common shell prefixes
            if word in ("cd", "echo", "{task}", "{model}", "{worktree}"):
                continue
            if word.startswith("--") or word.startswith("-"):
                continue
            if word.startswith("{"):
                continue
            # word is a candidate binary name
            return word
    return agent_name


def check_agent_health(agent_name: str, registry: dict | None = None) -> dict:
    """Check if an agent CLI is available and responsive."""
    if registry is None:
        registry = load_registry()

    agent_def = registry.get("agents", {}).get(agent_name)
    if not agent_def:
        return {"available": False, "cli_found": False, "error": f"Unknown agent: {agent_name}"}

    cli_template = agent_def.get("cli_template", "")
    binary = _find_cli_binary(cli_template, agent_name)

    cli_found = shutil.which(binary) is not None

    return {"available": cli_found, "cli_found": cli_found, "error": None}


def check_all_agents(registry: dict | None = None) -> dict:
    """Check health of all registered agents."""
    if registry is None:
        registry = load_registry()
    results = {}
    for agent_name in registry.get("agents", {}):
        results[agent_name] = check_agent_health(agent_name, registry)
    for agent_name, status in results.items():
        if status.get("available") and status.get("cli_found"):
            agent_def = registry.get("agents", {}).get(agent_name, {})
            models = agent_def.get("available_models", [])
            caps = set()
            for m in models:
                for c in m.get("capabilities", []):
                    caps.add(c)
            announce_capabilities(agent_name, sorted(caps), [m.get("id", "unknown") for m in models])
    return results
