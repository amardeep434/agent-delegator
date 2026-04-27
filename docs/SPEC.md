# delegator - Standalone Agent Delegation System

## Status

**⚠️ Partial Implementation** — Core engine files complete, 4 integration wiring gaps, 6 missing files, 3 missing CLI commands.

## Milestone Tracking

| Milestone | Status | Notes |
|----------|--------|-------|
| M1: Core Delegation (Phase 1) | ✅ Complete | executor.py, router.py, resolver.py, cooldowns, handoff, cleanup, registry |
| M2: CLI + All Features (Phase 2-3) | ⚠️ Partial | 9/12 CLI commands done; missing init, config, test |
| M3: Capabilities (Phase 4.2) | ✅ Complete | capabilities.py + capabilities.json |
| M4: Learned Routing (Phase 4.3) | ✅ Complete | optimizer.py + metrics.py |
| M5: Integration Wiring | ❌ NOT DONE | executor.py doesn't call metrics/handoff/optimizer |
| M6: Phase 2.1-2.2 (Streaming + Signals) | ❌ NOT DONE | --stream flag accepted but not functional |
| M7: Remaining Files + Docs | ❌ NOT DONE | 6 files missing (handoff-template, cleanup.sh, etc.) |
| M8: Integration Tests | ⚠️ Partial | 13 tests pass, 2 test suites missing |
| M9: VyapaarLink Migration | ❌ Not started | `.superpowers/delegation/` still exists, not migrated to `delegator exec` |

## Progress Summary

### Done
- Repo created at `github.com/amardeep434/delegator`
- All 14 Python source files implemented
- Registry: 5 agents, 3 logical models, 4 workflows, routing matrix, rate limit patterns
- 9 of 12 CLI commands implemented
- 13 unit tests passing (router, resolver, cooldowns, registry)
- All features have their .py files: executor, router, resolver, cooldowns, handoff, cleanup, metrics, capabilities, optimizer, health

### In Progress
- Integration wiring: executor.py doesn't yet call metrics/handoff/optimizer
- Phase 2.1-2.2: Streaming output + signal handling not implemented
- Missing CLI commands: init, config, test
- Missing files: handoff-template.md, cleanup.sh, capabilities-schema.json, README.md, INTEGRATION.md, docs/SPEC.md

### Blocked
- None

## Architecture

### Project Structure

```
delegator/
├── delegator/                  # Python package
│   ├── __main__.py            # python -m delegator
│   ├── __init__.py
│   ├── cli.py                 # ✅ CLI commands: exec, status, health, routes, model, cleanup, capabilities, optimize, learn, metrics
│   ├── executor.py            # ✅ Core execution + federated failover
│   ├── router.py              # ✅ Agent-agnostic routing engine
│   ├── resolver.py            # ✅ Model name resolution per provider
│   ├── registry.py            # ✅ Registry loader + merger (default + project override + env)
│   ├── models.py              # ✅ Data classes (DelegationRequest, DelegationResult, CooldownEntry)
│   ├── cooldowns.py           # ✅ Circuit breaker state (exponential backoff)
│   ├── handoff.py             # ✅ Context handoff generation (⚠️ not yet called from executor)
│   ├── cleanup.py              # ✅ Worktree TTL cleanup
│   ├── metrics.py              # ✅ SQLite metrics storage (⚠️ not yet called from executor)
│   ├── capabilities.py         # ✅ Capability announcements + discovery (⚠️ announce not auto-called)
│   ├── optimizer.py            # ✅ Learned routing (⚠️ not yet consulted by executor)
│   ├── health.py               # ✅ Proactive health checks
│   ├── state.py                # ✅ XDG-compliant state directory management
│   └── utils.py               # ✅ JSON helpers + deep merge
├── registry.json              # ✅ Default registry (5 agents, 3 logical models, 4 workflows)
├── handoff-template.md        # ❌ Not created yet
├── cleanup.sh                 # ❌ Not created yet
├── capabilities-schema.json   # ❌ Not created yet
├── pyproject.toml             # ✅ Setuptools config with CLI entry point
├── README.md                  # ❌ Not created yet
├── INTEGRATION.md             # ❌ Not created yet
├── tests/                     # ⚠️ Partial (4 suites exist, 2 missing)
│   ├── __init__.py            # ✅
│   ├── test_router.py        # ✅ 3 tests
│   ├── test_resolver.py      # ✅ 4 tests
│   ├── test_cooldowns.py     # ✅ 2 tests
│   ├── test_registry.py      # ✅ 4 tests
│   ├── test_federated.py     # ❌ Not created yet
│   └── test_integration.py   # ❌ Not created yet
└── docs/
    └── SPEC.md                # ❌ Not created yet
```

### Storage Locations

| Data | Location | Rationale |
|------|----------|-----------|
| Code | `~/.local/share/delegator/` or clone | Portable |
| Registry | Shipped + project override | Works out of box |
| Metrics | `~/.local/state/delegator/metrics.db` | Centralized across projects |
| Cooldowns | `~/.local/state/delegator/cooldowns.json` | Shared provider health |
| Worktrees | `<project>/.delegation/worktrees/` | Project-local, git proximity |

---

## Data Model

### Registry Schema

```json
{
  "version": "1.0",
  "agents": {
    "claude": {
      "name": "Claude CLI",
      "available_models": [
        {"id": "claude-sonnet-4-6", "display": "Sonnet 4.6", "capabilities": ["coding", "reasoning"]},
        {"id": "claude-haiku-4-5", "display": "Haiku 4.5", "capabilities": ["coding", "fast"]}
      ],
      "cli_template": "claude -p --model {model}"
    },
    "opencode": {
      "name": "OpenCode CLI",
      "available_models": [
        {"id": "minimax-m2.5-free", "display": "Minimax Free", "capabilities": ["coding", "free"]},
        {"id": "anthropic/claude-sonnet-4-6", "display": "Sonnet via OpenCode", "capabilities": ["coding", "reasoning"]}
      ],
      "cli_template": "opencode run --model {model}"
    },
    "copilot": {...},
    "codex": {...},
    "antigravity": {...}
  },
  "logical_models": {
    "federated-sonnet": {
      "display": "Any Sonnet",
      "providers": ["claude:claude-sonnet-4-6", "opencode:anthropic/claude-sonnet-4-6"]
    },
    "federated-coding": {
      "display": "Any Coding Model",
      "providers": ["claude:claude-sonnet-4-6", "opencode:minimax-m2.5-free"]
    }
  },
  "workflows": {
    "brainstorming": {
      "tasks": ["requirements", "architecture", "exploration"],
      "preferred_capabilities": ["reasoning"]
    },
    "writing-plans": {...},
    "subagent-driven": {
      "tasks": ["implementation", "testing", "code_review", "research"],
      "preferred_capabilities": ["coding"]
    },
    "verification": {...}
  },
  "routing_matrix": {
    "_any_agent_": {
      "subagent-driven": {
        "implementation": {"delegate_to": "opencode", "preferred_model": "minimax-m2.5-free"},
        "testing": {"delegate_to": "opencode", "preferred_model": "minimax-m2.5-free"},
        "code_review": {"delegate_to": "claude", "preferred_model": "claude-sonnet-4-6"}
      },
      "brainstorming": {
        "requirements": {"delegate_to": "claude", "preferred_model": "claude-sonnet-4-6"}
      }
    }
  },
  "provider_priority": ["claude", "opencode", "copilot", "codex", "antigravity"],
  "rate_limit_patterns": [
    "429", "rate.?limit", "too.?many.?requests", "rate_limit_exceeded",
    "quota.?exceeded", "max.?tokens", "tpm.?limit", "rpm.?limit",
    "hit.*limit", "limit.*reset", "overloaded", "insufficient_quota"
  ],
  "cooldown": {
    "failure_threshold": 3,
    "base_minutes": 5,
    "max_minutes": 60
  }
}
```

### Agent Configuration

Each agent has:
- `name`: Human-readable name
- `available_models`: List of supported models with capabilities
- `cli_template`: How to invoke with a model
- `health_check`: Optional endpoint for proactive health checks

### Model Resolution

| Agent | Naming Convention | Example |
|-------|-------------------|---------|
| claude | Direct names | `sonnet` → `claude-sonnet-4-6` |
| opencode | Provider prefix required | `minimax-m2.5-free` → `opencode/minimax-m2.5-free` |
| copilot | Standard OpenAI | `gpt-4.1` |
| codex | OpenAI subset | `gpt-4o-mini` |
| antigravity | Gemini-native | `gemini-3.1-pro-high` |

---

## CLI Interface

### Commands

```bash
# ===== Implemented =====
delegator exec [options]              # ✅ Execute delegation
  --model <model>                     # Logical model (e.g., federated-sonnet, sonnet)
  --task <task-description>           # Task to execute
  --workflow <workflow>               # Workflow type (default: subagent-driven)
  --from-agent <agent>                # Source agent (optional, for routing)
  --stream                            # ⚠️ Accepted but not implemented (Phase 2.1)
  --no-worktree                        # Skip worktree creation

delegator status                       # ✅ Show system status (cooldowns + metrics)
delegator health                       # ✅ Check agent availability
delegator routes                       # ✅ List available routes
delegator model <model>                # ✅ Show model details + providers
delegator cleanup [--project <path>] [--ttl <hours>]  # ✅ Clean up stale worktrees
delegator capabilities [--agent <name>] # ✅ Show capability announcements
delegator optimize                      # ✅ Analyze metrics and tune priorities
delegator learn                         # ✅ Learn from recent delegations
delegator metrics [--agent <name>] [--days <n>] [--limit <n>]  # ✅ Show metrics

# ===== Not Implemented =====
delegator init                         # ❌ Initialize .delegator.json in project
delegator config [key] [value]         # ❌ Get/set .delegator.json config
delegator test [--suite <name>]         # ❌ Run integration tests
  --from-file <file>                  # ❌ Read task from file (exec option)
  --output <file>                     # ❌ Redirect output to file (exec option)

delegator --help                      # Full help
```

### Examples

```bash
# Basic delegation
delegator exec --model federated-sonnet --task "Fix the login bug"

# With workflow
delegator exec --model sonnet --workflow brainstorming --task "Design auth system"

# From file
delegator exec --model haiku --from-file TASK.md --workflow subagent-driven

# Streaming output
delegator exec --model federated-coding --task "Add unit tests" --stream

# Check status
delegator status
delegator health
delegator routes
delegator model federated-sonnet
```

---

## Data Flow

```
delegator exec --model federated-sonnet --task "fix bug"
        │
        ▼
┌───────────────────────────────────────┐
│  cli.py - Parse arguments             │
│  Load registry (default + override)   │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  router.py - Resolve route            │
│  from_agent + workflow + task          │
│  → delegate_to, preferred_model        │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  resolver.py - Normalize model         │
│  federated-sonnet → best provider      │
│  sonnet → claude-sonnet-4-6           │
│  Apply CLI template                    │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  executor.py - Execute with failover  │
│  1. Try provider[0]                    │
│  2. On rate-limit → try provider[1]   │
│  3. On rate-limit → try provider[2]   │
│  4. Track cooldowns                    │
│  5. Write metrics                     │
└────────────────��──────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  Output:                              │
│  {                                    │
│    "success": true,                   │
│    "provider_used": "opencode",        │
│    "model_used": "anthropic/...",     │
│    "fallback_count": 1                │
│  }                                    │
└───────────────────────────────────────┘
```

---

## Integration Wiring (⚠️ Incomplete — executor.py must call these)

The following components exist but are NOT yet called from the execution flow. These must be wired into `executor.py`:

| Call | When | In | Detail |
|------|------|----|--------|
| `metrics.record_delegation()` | After each execution (success or failure) | `executor.py` | Records to SQLite, drives all analytics |
| `handoff.write_handoff()` | On agent failover (before switching) | `executor.py` | Writes HANDOFF.md so next agent has context |
| `optimizer.get_rankings()` | Before choosing provider order | `executor.py` | Re-orders logical model providers by learned scores |
| `capabilities.announce_capabilities()` | After health check passes | `health.py` | Auto-publishes capabilities from registry |

**Current executor flow (simplified):**
```
resolve_route → resolve_logical_model → for provider in providers:
    try: run CLI → check failure → next provider
    success: return result
```

**Target executor flow (with wiring):**
```
resolve_route → get_rankings (optimizer) → reorder providers →
for provider in sorted_providers:
    try: run CLI → check failure →
        write_handoff (to next agent) → next provider
    success:
        record_delegation (metrics) → return result
```

---

## Features

### 1. Agent-Agnostic Routing (router.py) ✅
- Any agent can delegate to any agent
- Routes based on workflow + task, not hardcoded pairs
- `_any_agent_` fallback for generic routes
- CLI: `delegator routes`

### 2. Federated Model Failover (executor.py) ✅
- Logical models map to multiple providers
- Automatic failover on rate-limit
- Per-request retry across providers
- CLI: `delegator exec`
- ⚠️ Integration: executor must call `optimizer.get_rankings()` before choosing providers

### 3. Circuit Breaker (cooldowns.py) ✅
- Tracks failures per (agent, model)
- 3 failures → 5 minute cooldown (configurable)
- Exponential backoff up to 60 min max
- Auto-recovery on success
- CLI: automatic (visible via `delegator status`)

### 4. Context Handoff (handoff.py) ✅
- Generates HANDOFF.md when switching agents
- Includes task summary + modified files
- Template: `handoff-template.md`
- ⚠️ Integration: executor must call `write_handoff()` on agent failover

### 5. Worktree Isolation (cleanup.py) ✅
- Git worktrees for clean delegation state
- TTL-based cleanup (24 hour default, configurable)
- Project-local: `<project>/.delegation/worktrees/`
- CLI: `delegator cleanup`

### 6. Capability-Based Routing (resolver.py) ✅
- Models tagged with capabilities
- Route by "I need fast coding" not "use this model"
- Fallback to capability match when no exact route
- Shorthand normalization: `sonnet` → `claude-sonnet-4-6`
- CLI: `delegator model`

### 7. Capability Announcements (capabilities.py) ✅
- Agents can publish their capabilities dynamically
- Location: `~/.local/state/delegator/capabilities.json`
- Auto-discovered via registry fallback if no announcements
- Enables routing by "who can do X" not just "who has model Y"
- CLI: `delegator capabilities`
- ⚠️ Integration: `announce_capabilities()` should auto-fire after health check

### 8. Learned Routing + Healing-Driven Optimization (optimizer.py) ✅
- Analyzes success rates from SQLite metrics database
- Auto-tunes provider priority based on performance (Phase 3.2: Healing-Driven Routing)
- Healing metrics drive fallback chain tuning
- Success/failure patterns inform routing decisions
- CLI: `delegator optimize`, `delegator learn`
- ⚠️ Integration: executor must consult `get_rankings()` for provider ordering

### 9. Proactive Health Checks (health.py) ✅
- Periodic lightweight ping to each agent CLI
- Updates capability availability in real-time
- Prevents cold-start failures on delegation
- CLI: `delegator health`

### 10. SQLite Metrics / Healing Analytics (metrics.py) ✅
- Phase 3.1: Replaces JSON-based healing-metrics.json with append-only SQLite
- Tracks: delegation_id, from_agent, to_agent, provider_used, success, fallback_count, duration
- Healing metrics drive routing optimization
- Fast queries for analytics: success rates, failure patterns, provider health
- CLI: `delegator metrics`
- ⚠️ Integration: executor must call `record_delegation()` after each run

### 11. Streaming Output (Phase 2.1) ❌
- Pipe agent output to `agent.log` in worktree
- Background `tail -f` for real-time streaming
- `--stream` flag accepted in CLI but not implemented in executor

### 12. Signal Handling (Phase 2.2) ❌
- `trap` SIGINT/SIGTERM to cleanup worktree on interrupt
- Graceful shutdown with worktree pruning
- Not yet implemented in executor

### 13. CLI-First Refactor (Phase 2.3) ✅
- Migration from `.superpowers/delegation/` MCP server to standalone CLI
- Subprocess invocation is primary execution path
- MCP mode available as optional fallback (`python-mcp` dependency)

### 14. Integration Tests (tests/) ⚠️ Partial
- Phase 3.3: Mock agents, test real failover paths
- ✅ `test_router.py` (3 tests) — routing resolution
- ✅ `test_resolver.py` (4 tests) — model normalization
- ✅ `test_cooldowns.py` (2 tests) — circuit breaker
- ✅ `test_registry.py` (4 tests) — registry loading
- ❌ `test_federated.py` — mock agent CLIs, verify failover order
- ❌ `test_integration.py` — end-to-end exec → metrics → optimize cycle
- CLI: `delegator test [--suite]` (not implemented)
- Total: 13/13 passing, 2 suites missing

---

## Integration with AI Agents

Any AI agent can invoke delegator via subprocess:

### From Claude CLI
```
claude -p "Use delegator to add unit tests"
echo "Add unit tests for OrderRepository" | delegator exec --model federated-coding --workflow subagent-driven --task implementation
```

### From OpenCode
```
opencode run "Add unit tests for OrderRepository" --task exec --model federated-coding
```

### From Custom Agent
```python
import subprocess

result = subprocess.run(
    ["delegator", "exec", "--model", "federated-sonnet",
     "--task", "Fix the login bug",
     "--workflow", "subagent-driven",
     "--from-agent", "claude"],
    capture_output=True, text=True
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    print(f"Provider: {data['provider_used']}")
```

---

## Project Configuration

Optional project config at `<project>/.delegator.json`:

```json
{
  "preferred_models": {
    "implementation": "federated-coding",
    "code_review": "claude:claude-sonnet-4-6"
  },
  "provider_priority": ["opencode", "claude", "copilot"],
  "worktree_ttl_hours": 12,
  "cooldown_minutes": 5
}
```

---

## State Management

### Cooldowns
Location: `~/.local/state/delegator/cooldowns.json`

```json
{
  "claude:claude-sonnet-4-6": {
    "failure_count": 2,
    "last_failure": "2026-04-26T10:00:00Z",
    "cooldown_until": null
  },
  "opencode:minimax-m2.5-free": {
    "failure_count": 0,
    "last_failure": null,
    "cooldown_until": null
  }
}
```

### Metrics (SQLite)
Location: `~/.local/state/delegator/metrics.db`

```sql
CREATE TABLE delegations (
    id TEXT PRIMARY KEY,
    from_agent TEXT,
    to_agent TEXT,
    model TEXT,
    provider_used TEXT,
    workflow TEXT,
    task TEXT,
    success BOOLEAN,
    fallback_count INTEGER,
    duration_ms INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Capabilities Announcement
Location: `~/.local/state/delegator/capabilities.json`

```json
{
  "claude": {
    "announced_at": "2026-04-26T10:00:00Z",
    "capabilities": ["coding", "reasoning", "planning", "fast"],
    "models_available": ["claude-sonnet-4-6", "claude-haiku-4-5"],
    "health_status": "available",
    "success_rate": 0.92
  },
  "opencode": {
    "announced_at": "2026-04-26T10:00:00Z",
    "capabilities": ["coding", "free"],
    "models_available": ["minimax-m2.5-free", "gpt-5-nano"],
    "health_status": "available",
    "success_rate": 0.88
  }
}
```

### Learned Routing Data
Location: `~/.local/state/delegator/provider_rankings.json`

```json
{
  "last_optimized": "2026-04-26T10:00:00Z",
  "rankings": {
    "federated-sonnet": [
      {"agent": "opencode", "model": "anthropic/claude-sonnet-4-6", "score": 0.95},
      {"agent": "claude", "model": "claude-sonnet-4-6", "score": 0.88}
    ],
    "federated-coding": [
      {"agent": "opencode", "model": "minimax-m2.5-free", "score": 0.92},
      {"agent": "claude", "model": "claude-haiku-4-5", "score": 0.85}
    ]
  }
}
```

---

## Dependencies

- Python 3.10+
- Standard library only (no external dependencies for core)
- Optional: `requests` for HTTP-based agent health checks
- Optional: `python-mcp` for MCP server mode

---

## Installation

```bash
# Clone repo
git clone https://github.com/amardeep434/delegator.git ~/.local/share/delegator

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/share/delegator:$PATH"

# Or install via pip (when published)
pip install delegator

# Initialize (optional)
delegator init
```

---

## Migration from Project-Embedded System

The current `.superpowers/delegation/` in VyapaarLink will:
1. Move to standalone `delegator` repo
2. Extract reusable components
3. Add project-independent features
4. VyapaarLink will become a consumer of `delegator`

---

## TODO

### Done
- [x] Create GitHub repo (`github.com/amardeep434/delegator`)
- [x] Implement core package structure (all .py files)
- [x] Add comprehensive registry (5 agents, 3 logical models, 4 workflows)
- [x] Implement 9 of 12 CLI commands (exec, status, health, routes, model, cleanup, capabilities, optimize, learn, metrics)
- [x] Implement SQLite metrics (delegator/metrics.py)
- [x] Implement capability announcements (delegator/capabilities.py)
- [x] Implement healing-driven routing optimization (delegator/optimizer.py)
- [x] Implement proactive health checks (delegator/health.py)
- [x] Write partial integration tests (13 tests, 4 suites)

### Phase A: Wiring (executor.py integration)
- [ ] Wire `metrics.record_delegation()` into executor.py (after each run)
- [ ] Wire `handoff.write_handoff()` into executor.py (on agent failover)
- [ ] Wire `optimizer.get_rankings()` into executor.py (before provider ordering)
- [ ] Wire `capabilities.announce_capabilities()` into health.py (after health check)

### Phase B: Missing CLI Commands
- [ ] Implement `delegator init` — creates `.delegator.json` template
- [ ] Implement `delegator config [key] [value]` — read/write `.delegator.json`
- [ ] Implement `delegator test [--suite]` — run pytest on named suite
- [ ] Add `--from-file` option to `delegator exec`
- [ ] Add `--output` option to `delegator exec`

### Phase C: Phase 2 Completion
- [ ] Implement streaming output (`--stream` → pipe to log + background tail)
- [ ] Implement signal handling (SIGINT/SIGTERM cleanup worktree)

### Phase D: Remaining Files
- [ ] Create `handoff-template.md`
- [ ] Create `cleanup.sh` (cron-ready script)
- [ ] Create `capabilities-schema.json`
- [ ] Create `README.md`
- [ ] Create `INTEGRATION.md` (agent integration guide)
- [ ] Create `docs/SPEC.md`

### Phase E: Remaining Tests
- [ ] Write `tests/test_federated.py` — mock agent CLIs, verify failover order
- [ ] Write `tests/test_integration.py` — end-to-end exec → metrics → optimize cycle

### Future (Optional)
- [ ] Publish to PyPI
- [ ] MCP server mode (`python-mcp`)