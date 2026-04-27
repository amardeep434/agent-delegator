"""Tests for dashboard API endpoints."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delegator.dashboard.api import get_status, get_metrics, get_routes, get_config, get_logs


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
    from delegator.dashboard.api import post_exec
    result = post_exec({"task": ""})
    assert result["status"] == "error"


def test_post_exec_rejects_long_task():
    from delegator.dashboard.api import post_exec
    result = post_exec({"task": "x" * 6000})
    assert result["status"] == "error"
