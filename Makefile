.PHONY: install test clean help

install:
	pip install -e .

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -f .delegator.json agent_*.log HANDOFF.md

help:
	@echo "delegator - Agent-agnostic AI CLI delegation"
	@echo ""
	@echo "  make install   Install delegator globally (pip install -e .)"
	@echo "  make test      Run all tests"
	@echo "  make clean     Clean build/test artifacts"
