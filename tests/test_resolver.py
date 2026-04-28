"""Tests for model resolver."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_delegator.resolver import normalize_model, resolve_logical_model, resolve_model
from agent_delegator.registry import load_registry


def test_normalize_sonnet_claude():
    registry = load_registry(force_reload=True)
    result = normalize_model("sonnet", "claude", registry)
    assert result == "claude-sonnet-4-6"


def test_normalize_haiku_claude():
    registry = load_registry(force_reload=True)
    result = normalize_model("haiku", "claude", registry)
    assert result == "claude-haiku-4-5"


def test_normalize_exact_match():
    registry = load_registry(force_reload=True)
    result = normalize_model("claude-sonnet-4-6", "claude", registry)
    assert result == "claude-sonnet-4-6"


def test_resolve_logical_model():
    registry = load_registry(force_reload=True)
    providers = resolve_logical_model(registry, "federated-sonnet")
    assert len(providers) > 0
    assert any("claude-sonnet-4-6" in p for p in providers)
