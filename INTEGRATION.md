# Integrating agent-delegator into AI Agent Workflows

## Overview

`agent-delegator` is called via subprocess by any AI agent. It handles routing, failover, and worktree isolation transparently.

## From Claude CLI

```bash
agent-delegator exec --model federated-coding --workflow subagent-driven --from-agent claude --task "Add unit tests for OrderRepository"
```

## From OpenCode

```bash
agent-delegator exec --model federated-coding --task "Add unit tests for OrderRepository"
```

## From Any Custom Agent

```python
import subprocess, json

result = subprocess.run(
    ["agent-delegator", "exec",
     "--model", "federated-sonnet",
     "--task", "Fix the login bug",
     "--from-agent", "claude"],
    capture_output=True, text=True
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    print(f"Provider: {data['provider_used']}, Model: {data['model_used']}")
```

## Federated Models

Logical models resolve to multiple providers with automatic failover:

| Model | Providers |
|-------|-----------|
| `federated-sonnet` | Claude, OpenCode, Copilot |
| `federated-coding` | Claude, OpenCode, Codex |
| `federated-free` | OpenCode, Copilot, Antigravity |

## Self-Healing Flow

1. `agent-delegator exec` resolves route
2. Consults learned rankings from SQLite metrics
3. Tries providers in ranked order
4. On rate-limit: applies cooldown, generates HANDOFF.md, switches to next provider
5. On success: records metrics, updates learned rankings

## Configuration

Environment variable override:
```bash
AGENT_DELEGATOR_PROVIDER_PRIORITY="opencode,claude,copilot" agent-delegator exec ...
```
