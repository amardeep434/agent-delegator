"""Tests for routing engine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_delegator.router import resolve_route
from agent_delegator.registry import load_registry


def test_resolve_route_implementation():
    registry = load_registry(force_reload=True)
    agent, model = resolve_route(registry, "subagent-driven", "implementation")
    assert agent == "opencode"
    assert model == "federated-coding"


def test_resolve_route_code_review():
    registry = load_registry(force_reload=True)
    agent, model = resolve_route(registry, "subagent-driven", "code_review")
    assert agent == "opencode"
    assert model == "federated-coding"


def test_resolve_route_fallback():
    registry = load_registry(force_reload=True)
    agent, model = resolve_route(registry, "unknown_workflow", "unknown_task")
    assert agent in registry.get("provider_priority", [])
