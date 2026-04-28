# agent-delegator

> Agent-agnostic AI CLI delegation with **federated model failover**, **intelligent routing**, and a **real-time Mission Control dashboard**.

[![CI](https://github.com/amardeep434/agent-delegator/actions/workflows/ci.yml/badge.svg)](https://github.com/amardeep434/agent-delegator/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agent-delegator)](https://pypi.org/project/agent-agent-delegator/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Why agent-delegator?

You have multiple AI agents installed — Claude, OpenCode, Copilot, Codex, Gemini — but switching between them is manual, error-prone, and wastes time. **agent-delegator** solves this by:

- **Failing over automatically** when an agent is down, rate-limited, or returns errors
- **Routing intelligently** based on workflow type (code review → Claude, implementation → OpenCode)
- **Learning from history** to prioritize the best agent for each task type
- **Monitoring everything** in a beautiful local dashboard with real-time metrics

No more copy-pasting prompts between chat windows. No more discovering your preferred agent is down *after* you sent a task. Just describe what you want and let agent-delegator pick the best available agent.

---

## Features

### Core Engine

| Feature | Description |
|---------|-------------|
| **Federated Failover** | Automatically falls back to the next best agent when the primary fails |
| **Intelligent Routing** | Route `implementation` tasks to OpenCode, `code_review` to Claude based on a configurable matrix |
| **Health Checks** | Continuously monitors agent availability and marks unhealthy agents for cooldown |
| **Circuit Breaker** | Temporarily disables failing agents to prevent cascading failures |
| **Auto-Learning** | Analyzes past delegations to optimize agent rankings and priority order |
| **Metrics & Cost Tracking** | Tracks success rates, duration, fallback counts, and estimated costs per agent |
| **Project Scoping** | Per-project `.agent-delegator.json` configs with isolated state and routing rules |

### Mission Control Dashboard

A local-only web UI (no cloud, no sign-up) that runs on `http://127.0.0.1:8765`:

| Feature | Description |
|---------|-------------|
| **Live Task Monitor** | Watch active tasks in real-time with auto-refreshing output |
| **Agent Health Cards** | Visual status of all agents with success-rate progress bars |
| **Delegation History** | Filterable table with replay, retry, and "like" functionality |
| **Analytics** | 7/14/30-day success rates, cost breakdowns, failure type charts, agent rankings |
| **A/B Model Comparison** | Run the same task on two models side-by-side and compare results |
| **Task Queue** | Queue tasks for later or schedule them with cron expressions |
| **Route Editor** | Drag-and-drop provider priority, add/remove workflow routes |
| **Notifications** | Telegram and Slack webhooks for task completion, failures, and cooldown alerts |
| **Project Switcher** | Switch between projects without leaving the dashboard |
| **Keyboard Shortcuts** | Vim-like shortcuts (`L` live, `O` logs, `H` history, `Cmd+K` exec) |

### Security

Built with a security-first mindset for a tool that processes code and executes commands:

- **API Key Authentication** on all dashboard endpoints
- **CSRF Protection** via Origin/Referer validation + `X-Requested-With`
- **Rate Limiting** using direct IP (no `X-Forwarded-For` trust)
- **XSS Prevention** — all dynamic DOM content escaped, no inline `onclick` with user data
- **SSRF Protection** — blocks localhost, private IPs, and metadata endpoints for webhooks
- **Input Validation** — shell metacharacters blocked, length limits enforced
- **Encrypted Secrets** — Fernet encryption for Telegram tokens and Slack URLs at rest
- **Security Headers** — CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy

---

## Supported Agents

| Agent | CLI Command | Status |
|-------|-------------|--------|
| Claude | `claude` | ✅ Supported |
| OpenCode | `opencode` | ✅ Supported |
| GitHub Copilot | `copilot` | ✅ Supported |
| Codex | `codex` | ✅ Supported |
| Gemini (Antigravity) | `antigravity` | ✅ Supported |

Adding a new agent requires only a few lines in `.agent-delegator.json`. See [INTEGRATION.md](INTEGRATION.md) for details.

---

## Install

### Quick Install (recommended)

```bash
pip install agent-delegator
```

This includes the full package with the Mission Control dashboard. The dashboard requires **zero extra dependencies** — it's pure Python stdlib + static HTML.

### Development Install

```bash
git clone https://github.com/amardeep434/agent-delegator.git
cd agent-delegator
pip install -e ".[dev]"
```

### Optional Dependencies

```bash
# With encryption support for dashboard secrets (recommended)
pip install "agent-delegator[secure]"

# Development + testing + building
pip install "agent-delegator[dev]"
```

### Skip the Dashboard

If you only want the CLI and never use the dashboard, disable it at runtime:

```bash
# One-time
AGENT_DELEGATOR_NO_DASHBOARD=1 agent-delegator dashboard

# Session-wide
export AGENT_DELEGATOR_NO_DASHBOARD=1

# Or disable per-project
agent-delegator init
# Edit .agent-delegator.json: "disable_dashboard": true
```

---

## Quick Start

### 1. Initialize your project

```bash
cd my-project
agent-delegator init
```

This creates `.agent-delegator.json` with sensible defaults.

### 2. Execute a task with automatic failover

```bash
agent-delegator exec --model federated-coding --task "Add unit tests for OrderRepository"
```

`federated-coding` is a logical model that tries the best available coding agent, falling back automatically.

### 3. Check system status

```bash
agent-delegator status
agent-delegator health
```

### 4. Launch the dashboard

```bash
agent-delegator dashboard
# Open http://127.0.0.1:8765
```

### 5. Learn from past delegations

```bash
agent-delegator learn
```

This re-ranks your agents based on success rates and response times.

---

## CLI Reference

```bash
# Execute with options
agent-delegator exec --model claude-sonnet-4-6 --task "Refactor this function" --stream

# Route a specific workflow
agent-delegator exec --model federated-coding --workflow code_review --task "Review PR #42"

# View metrics
agent-delegator metrics --days 7 --agent opencode

# Optimize rankings manually
agent-delegator optimize

# Clean up stale worktrees
agent-delegator cleanup --ttl 24

# Check capabilities of an agent
agent-delegator capabilities --agent claude
```

### Global Flags

| Flag | Description |
|------|-------------|
| `--no-dashboard` | Disable dashboard features for this session |

---

## Configuration

### Project Config (`.agent-delegator.json`)

```json
{
  "preferred_models": {
    "implementation": "federated-coding",
    "code_review": "claude:claude-sonnet-4-6",
    "research": "federated-sonnet"
  },
  "provider_priority": ["opencode", "claude", "copilot"],
  "worktree_ttl_hours": 24,
  "cooldown": {
    "failure_threshold": 3,
    "base_minutes": 5,
    "max_minutes": 60
  },
  "disable_dashboard": false
}
```

### Routing Matrix

Define which agent handles which workflow/task combination:

```json
{
  "routing_matrix": {
    "_any_agent_": {
      "subagent-driven": {
        "implementation": {
          "delegate_to": "opencode",
          "preferred_model": "federated-coding"
        },
        "code_review": {
          "delegate_to": "claude",
          "preferred_model": "claude-sonnet-4-6"
        }
      }
    }
  }
}
```

---

## How It Works

```
User Request
    │
    ▼
┌─────────────────┐
│  Route Resolver │──→ Match workflow/task against routing matrix
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Health Check   │──→ Is the preferred agent available?
└─────────────────┘
    │ Yes          │ No
    ▼              ▼
┌────────┐    ┌─────────────────┐
│ Execute│    │  Failover Loop  │──→ Try next agent in priority order
└────────┘    └─────────────────┘
    │
    ▼
┌─────────────────┐
│  Record Metrics │──→ Success rate, duration, cost, fallback count
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Notify (opt)   │──→ Telegram/Slack webhook
└─────────────────┘
```

---

## Dashboard Screenshots

The dashboard provides a single-pane-of-glass view into all your AI agent activity:

- **Live View** — Real-time output from active tasks with auto-polling
- **Logs** — Searchable, filterable delegation history with error highlighting
- **Analytics** — Bar charts for success rates, cost breakdowns, failure classifications
- **Compare** — Side-by-side A/B testing of two models on the same prompt
- **Queue** — Manage pending and scheduled tasks
- **Settings** — Drag-and-drop provider priority, circuit breaker config, notification setup

All data stays local. The dashboard binds to `127.0.0.1` only and uses a machine-bound API key for authentication.

---

## Development

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Dashboard tests only
python -m pytest tests/test_dashboard.py tests/test_dashboard_security.py -v

# Security regression tests
python -m pytest tests/test_dashboard_security.py -v
```

### Building

```bash
python -m build
```

### Project Structure

```
agent-delegator/
├── cli.py              # CLI entry point
├── executor.py         # Task execution & failover logic
├── router.py           # Workflow → agent routing
├── resolver.py         # Logical model → provider resolution
├── registry.py         # Agent configuration & routing matrix
├── health.py           # Agent health checks
├── cooldowns.py        # Circuit breaker & cooldown management
├── metrics.py          # Delegation metrics & success tracking
├── optimizer.py        # Auto-learning & ranking optimization
├── dashboard/
│   ├── server.py       # HTTP server with auth & security headers
│   ├── api.py          # REST API endpoints
│   └── templates/
│       └── dashboard.html  # Mission Control UI
└── secrets.py          # Fernet encryption for sensitive config
```

---

## Release Automation

This project uses **GitHub Actions** for continuous delivery:

1. **CI Workflow** — Runs tests on Python 3.10–3.13 for every PR and push
2. **Release Workflow** — Auto-bumps version based on [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` → minor version bump
   - `fix:` → patch version bump
   - `BREAKING CHANGE:` → major version bump
3. **PyPI Publishing** — Builds and publishes automatically on version bump

### Setup (one-time)

1. Go to [PyPI Account Settings → API Tokens](https://pypi.org/manage/account/#api-tokens)
2. Create a token scoped to the `agent-delegator` project
3. In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**
4. Name: `PYPI_API_TOKEN`, Value: your token

### Trigger a Release

Merge a PR with a [Conventional Commit](https://www.conventionalcommits.org/) message:

```bash
git commit -m "feat: add Gemini agent support"
git push origin main
# → Workflow detects feat: → bumps minor → publishes v0.2.0
```

---

## Security

See [AGENTS.md](AGENTS.md) for the full security checklist and development guidelines.

If you discover a security vulnerability, please email amardeep434@gmail.com rather than opening a public issue.

---

## License

MIT © [Amardeep](https://github.com/amardeep434)

---

## Acknowledgments

Built with inspiration from:
- [Aider](https://aider.chat/) — AI pair programming
- [Fabric](https://github.com/danielmiessler/fabric) — AI pattern framework
- [OpenRouter](https://openrouter.ai/) — Unified LLM API
