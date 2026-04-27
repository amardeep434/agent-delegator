"""Proactive health checks for agent availability."""

import subprocess
from delegator.registry import load_registry


def check_agent_health(agent_name: str, registry: dict | None = None) -> dict:
    """Check if an agent CLI is available and responsive."""
    if registry is None:
        registry = load_registry()

    agent_def = registry.get("agents", {}).get(agent_name)
    if not agent_def:
        return {"available": False, "cli_found": False, "error": f"Unknown agent: {agent_name}"}

    cli_template = agent_def.get("cli_template", "")
    cli_name = cli_template.split(" ")[0] if cli_template else ""

    try:
        result = subprocess.run(
            ["which", cli_name] if cli_name else ["true"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {"available": False, "cli_found": False, "error": f"CLI not found: {cli_name}"}
    except Exception as e:
        return {"available": False, "cli_found": False, "error": str(e)}

    return {"available": True, "cli_found": True, "error": None}


def check_all_agents(registry: dict | None = None) -> dict:
    """Check health of all registered agents."""
    if registry is None:
        registry = load_registry()
    results = {}
    for agent_name in registry.get("agents", {}):
        results[agent_name] = check_agent_health(agent_name, registry)
    return results
