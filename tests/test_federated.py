"""Integration tests for federated failover with mocked agent CLIs."""
import sys, os, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delegator.executor import _check_rate_limit, _check_failure

def test_rate_limit_pattern_matching():
    registry = {
        "rate_limit_patterns": ["429", "rate.?limit", "quota.?exceeded", "too.?many.?requests"]
    }
    assert _check_rate_limit("Error 429: rate limit exceeded", registry) is True
    assert _check_rate_limit("Success: build complete", registry) is False
    assert _check_rate_limit("Error: quota exceeded", registry) is True
    assert _check_rate_limit("too many requests in window", registry) is True


def test_check_failure_file(tmp_path):
    registry = {"rate_limit_patterns": ["429", "rate.?limit"]}
    log = tmp_path / "agent_0.log"
    log.write_text("Error 429: rate limit exceeded")
    assert _check_failure(str(log), registry) is True


def test_check_failure_file_success(tmp_path):
    registry = {"rate_limit_patterns": ["429", "rate.?limit"]}
    log = tmp_path / "agent_0.log"
    log.write_text("Build completed successfully")
    assert _check_failure(str(log), registry) is False


def test_check_failure_missing_file():
    assert _check_failure("/nonexistent/path/agent.log", {"rate_limit_patterns": []}) is True


def test_fallback_order_with_rankings():
    from delegator.optimizer import get_rankings
    from delegator.state import rankings_path
    from delegator.utils import save_json

    test_rankings = {
        "last_optimized": "2026-04-27T00:00:00Z",
        "rankings": {
            "opencode": {"score": 0.95, "total_delegations": 100},
            "claude": {"score": 0.60, "total_delegations": 100},
            "copilot": {"score": 0.80, "total_delegations": 100},
        },
        "recommended_priority": ["opencode", "copilot", "claude"],
    }
    save_json(str(rankings_path()), test_rankings)

    rankings = get_rankings()
    assert rankings == test_rankings

    providers = ["claude:claude-sonnet-4-6", "opencode:anthropic/claude-sonnet-4-6", "copilot:claude-sonnet-4-6"]
    scored = []
    for pk in providers:
        parts = pk.split(":", 1)
        if len(parts) == 2:
            score = rankings.get("rankings", {}).get(parts[0], {}).get("score", 0.0)
            scored.append((pk, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    sorted_providers = [s[0] for s in scored]

    assert sorted_providers[0] == "opencode:anthropic/claude-sonnet-4-6"
    assert sorted_providers[1] == "copilot:claude-sonnet-4-6"
    assert sorted_providers[2] == "claude:claude-sonnet-4-6"
