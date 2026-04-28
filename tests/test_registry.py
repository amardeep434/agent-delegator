"""Tests for registry loading and merging."""

import json
import tempfile
import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_delegator.registry import load_registry, get_agent, get_route
from agent_delegator.utils import deep_merge


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"d": 3}, "e": 4}
    result = deep_merge(base, override)
    assert result["a"] == 1
    assert result["b"]["c"] == 2
    assert result["b"]["d"] == 3
    assert result["e"] == 4


def test_load_registry_default():
    registry = load_registry(force_reload=True)
    assert "version" in registry
    assert "claude" in registry.get("agents", {})
    assert "opencode" in registry.get("agents", {})


def test_get_agent():
    registry = load_registry(force_reload=True)
    claude = get_agent(registry, "claude")
    assert claude is not None
    assert "available_models" in claude


def test_get_route():
    registry = load_registry(force_reload=True)
    route = get_route(registry, "subagent-driven", "implementation")
    assert route is not None
    assert "delegate_to" in route
    assert "preferred_model" in route
