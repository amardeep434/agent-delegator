"""Tests for circuit breaker cooldowns."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delegator.cooldowns import is_cooled_down, record_failure, record_success


def test_not_cooled_down_initially():
    assert not is_cooled_down("test_agent", "test_model")


def test_record_failure_then_cooldown():
    registry = {"cooldown": {"failure_threshold": 1, "base_minutes": 5, "max_minutes": 60}}
    record_failure("test_agent_cd", "test_model_cd", registry)
    assert is_cooled_down("test_agent_cd", "test_model_cd")
    record_success("test_agent_cd", "test_model_cd")
    assert not is_cooled_down("test_agent_cd", "test_model_cd")
