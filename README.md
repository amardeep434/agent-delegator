# delegator

Agent-agnostic AI CLI delegation with federated model failover.

## Install

```bash
git clone https://github.com/amardeep434/delegator.git ~/.local/share/delegator
echo 'export PATH="$HOME/.local/share/delegator/delegator:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Or via pip:
```bash
pip install git+https://github.com/amardeep434/delegator.git
```

## Quick Start

```bash
# Check agent health
delegator health

# Execute a task with federated failover
delegator exec --model federated-coding --task "Add unit tests for OrderRepository"

# Check status
delegator status

# Clean up stale worktrees
delegator cleanup --ttl 24
```

## Commands

| Command | Description |
|---------|-------------|
| `exec` | Execute delegation with federated failover |
| `status` | Show system status (cooldowns, metrics) |
| `health` | Check agent availability |
| `routes` | List available routes |
| `model` | Show model details and providers |
| `cleanup` | Clean up stale worktrees |
| `capabilities` | Show capability announcements |
| `optimize` | Analyze metrics and tune priorities |
| `learn` | Learn from recent delegations |
| `metrics` | Show delegation metrics |
| `init` | Initialize .delegator.json |
| `config` | Get/set configuration |
| `test` | Run integration tests |

## Project Config

Create `.delegator.json` in your project to override defaults:

```json
{
  "preferred_models": {
    "implementation": "federated-coding",
    "code_review": "claude:claude-sonnet-4-6"
  },
  "provider_priority": ["opencode", "claude", "copilot"],
  "worktree_ttl_hours": 12
}
```

## Supported Agents

- Claude CLI
- OpenCode CLI
- GitHub Copilot CLI
- Codex CLI
- Antigravity (Gemini CLI)

See [INTEGRATION.md](INTEGRATION.md) for how to integrate delegator into your AI agent workflows.
