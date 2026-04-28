"""Tests for dashboard API endpoints."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_delegator.dashboard.api import get_status, get_metrics, get_routes, get_config, get_logs


def test_get_status_returns_agents():
    data = get_status()
    assert "agents" in data
    assert "success_rate" in data
    assert "cooldowns" in data
    assert len(data["agents"]) >= 1


def test_get_metrics_returns_data():
    data = get_metrics(agent="opencode", days=7)
    assert "success_rate" in data
    assert "delegations" in data
    assert isinstance(data["total"], int)


def test_get_routes_has_all_workflows():
    data = get_routes()
    assert "routes" in data
    assert len(data["routes"]) >= 5
    workflows = [r["workflow"] for r in data["routes"]]
    assert "subagent-driven" in workflows


def test_get_config_has_priority():
    data = get_config()
    assert "provider_priority" in data
    assert isinstance(data["provider_priority"], list)


def test_get_logs_limits():
    data = get_logs(limit=10)
    assert "entries" in data
    assert len(data["entries"]) <= 10


def test_post_exec_rejects_empty_task():
    from agent_delegator.dashboard.api import post_exec
    result = post_exec({"task": ""})
    assert result["status"] == "error"


def test_post_exec_rejects_long_task():
    from agent_delegator.dashboard.api import post_exec
    result = post_exec({"task": "x" * 6000})
    assert result["status"] == "error"


def test_compare_returns_status_ok():
    from agent_delegator.dashboard.api import post_compare
    from agent_delegator.models import DelegationResult
    from unittest.mock import patch

    mock_result = DelegationResult(
        success=True, provider_used="opencode", model_used="opencode-go/deepseek-v4-pro",
        fallback_count=0, output="42", duration_ms=123, request_id="abc"
    )
    with patch("agent_delegator.dashboard.api.execute", return_value=mock_result):
        result = post_compare({"task": "what is 6*7"})
    assert result["status"] == "ok"
    assert "results" in result
    assert "A" in result["results"]
    assert "B" in result["results"]


def test_compare_results_have_expected_fields():
    from agent_delegator.dashboard.api import post_compare
    from agent_delegator.models import DelegationResult
    from unittest.mock import patch

    mock_result = DelegationResult(
        success=False, provider_used="claude", model_used="claude-sonnet-4-6",
        fallback_count=2, error="rate limit", output=None, duration_ms=5000, request_id="xyz"
    )
    with patch("agent_delegator.dashboard.api.execute", return_value=mock_result):
        result = post_compare({"task": "test"})

    for label in ("A", "B"):
        r = result["results"][label]
        assert "model" in r
        assert "success" in r
        assert "provider" in r
        assert "duration_ms" in r
        assert "fallback_count" in r
        assert "output" in r


def test_compare_handles_execute_exception():
    from agent_delegator.dashboard.api import post_compare
    from unittest.mock import patch

    with patch("agent_delegator.dashboard.api.execute", side_effect=RuntimeError("agent unavailable")):
        result = post_compare({"task": "failing task"})

    assert result["status"] == "ok"
    for label in ("A", "B"):
        assert "error" in result["results"][label]
