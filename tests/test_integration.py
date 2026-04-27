"""End-to-end integration tests for delegator."""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delegator.registry import load_registry
from delegator.router import resolve_route
from delegator.resolver import resolve_logical_model, normalize_model, build_cli_command
from delegator.metrics import record_delegation, get_success_rate, get_recent_delegations, clear_delegations
from delegator.optimizer import optimize_rankings, get_rankings


def test_full_exec_to_metrics_to_optimize_cycle():
    # 1. Load registry
    registry = load_registry(force_reload=True)
    assert "version" in registry

    # 2. Resolve route
    agent, model = resolve_route(registry, "subagent-driven", "implementation")
    assert agent == "opencode"
    assert model == "federated-coding"

    # 3. Resolve logical model to providers
    providers = resolve_logical_model(registry, model)
    assert len(providers) > 0

    # 4. Normalize model for agent
    resolved = normalize_model("sonnet", "claude", registry)
    assert resolved == "claude-sonnet-4-6"

    # 5. Build CLI command
    cmd = build_cli_command(registry, "opencode", "opencode/minimax-m2.5-free", "Test task", "/tmp/test")
    assert "opencode/minimax-m2.5-free" in cmd
    assert "Test task" in cmd

    # 6. Clear old data, then record synthetic delegations
    clear_delegations()
    for i in range(5):
        record_delegation(
            request_id=f"test_{i}",
            from_agent="claude",
            to_agent="opencode",
            model="minimax-m2.5-free",
            provider_used="opencode",
            workflow="subagent-driven",
            task_type="implementation",
            success=i < 4,  # 4 successes, 1 failure
            fallback_count=0,
            duration_ms=1000,
        )

    # 7. Check success rate
    rate = get_success_rate(agent="opencode")
    assert rate == 0.8  # 4/5

    # 8. Check recent delegations
    recent = get_recent_delegations(limit=10)
    assert len(recent) >= 5

    # 9. Optimize rankings
    rankings = optimize_rankings()
    assert "rankings" in rankings
    assert "recommended_priority" in rankings

    # 10. Get rankings
    saved = get_rankings()
    assert saved == rankings
