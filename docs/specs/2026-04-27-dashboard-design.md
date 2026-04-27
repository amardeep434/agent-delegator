# Delegator Mission Control Dashboard — Design Specification

**Created:** 2026-04-27  
**Status:** Design Complete — Awaiting Implementation Plan  
**Mockup:** `mockups/dashboard-mockup.html` (open in browser)

## Overview

A local-first, zero-dependency browser dashboard for monitoring, managing, and executing AI agent delegations. Runs entirely on localhost — no data leaves the machine. Served by a lightweight Python HTTP server built into the existing `delegator` CLI package.

## Design Principles

1. **Local-first** — All data stays on localhost. No cloud, no telemetry, no external APIs.
2. **Show what's wrong first** — Alert bar at top, agent cards with color-coded health, cooldowns visible
3. **One-click action** — Stop a running task, retry a failed one, auto-heal all cooldowns
4. **Keyboard-driven** — Power users navigate entirely via keyboard shortcuts
5. **OLED-optimized dark theme** — `#020617` background, `#22C55E` terminal green accents, JetBrains Mono

## Architecture

```
delegator/
├── delegator/
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── server.py        # HTTP server (stdlib http.server)
│   │   ├── api.py            # JSON API endpoints
│   │   └── templates/
│   │       └── dashboard.html  # Self-contained UI (no CDN)
│   ├── cli.py                # MODIFY: add `dashboard` subcommand
│   └── ...
├── mockups/
│   └── dashboard-mockup.html # Design mockup (not shipped in package)
```

### Data Flow

```
Browser (localhost:8765)
    │
    │ GET /          → dashboard.html (static)
    │ GET /api/status → JSON: agents, tasks, cooldowns, success rates
    │ GET /api/metrics → JSON: delegation history, analytics
    │ GET /api/logs  → JSON: streaming log entries
    │ POST /api/exec → JSON: execute delegation, return streaming output
    │ GET /api/routes → JSON: routing matrix
    │ GET /api/config → JSON: current configuration
    │ POST /api/config → JSON: update configuration
    │ POST /api/tasks/:id/stop → JSON: stop running task
    │
    ▼
Python HTTP server (dashboard/server.py)
    │
    │ reads → ~/.local/state/delegator/metrics.db (SQLite)
    │ reads → ~/.local/state/delegator/cooldowns.json
    │ reads → ~/.local/state/delegator/capabilities.json
    │ calls → delegator.executor.execute()
    │ calls → delegator.metrics.*()
    │ calls → delegator.registry.load_registry()
```

### Security

| Measure | Detail |
|---------|--------|
| Bind address | `127.0.0.1` only — no external network access |
| No auth | Not needed — localhost-only, same as `delegator` CLI |
| No CORS | Same-origin requests only |
| Input validation | `shlex.quote()` on exec task input, path validation on file reads |
| Port | Configurable via `--port`, default `8765` |

## Features

### 1. Header
- Project name, status indicator, theme toggle (dark/light)
- Multi-project switcher (F7)
- Auto-Heal button, keyboard shortcut hint (⌘K)

### 2. Alert Bar
- Shows only when there are failures/cooldowns/quota issues
- Rate limit reset predictor: "rate limits reset in 23m (claude), 8m (opencode)"
- Auto-Heal All + Dismiss buttons

### 3. Metrics Row (8 cards)
Active Agents, Running Tasks, 7d Delegations, Success Rate, Active Cooldowns, Queued Tasks, Routes, Est. Cost

### 4. Active Tasks Banner
- Always visible, collapsible, shows all running tasks
- Per-task: task ID, agent/model, description, progress bar, elapsed time, est. cost, Stop button
- Green highlight on selected task
- Click to open Live View

### 5. Agent Cards (left rail)
- Per-agent: health dot, current model, success rate bar, delegation count, est. cost
- Click opens modal with all models, capabilities, per-model stats

### 6. Tabs (8)

| Tab | Purpose |
|-----|---------|
| **Live** | Terminal-style streaming output for selected active task |
| **Logs** | Real-time log stream with classifications, filter bar, metrics sidebar |
| **History** | Filterable delegation table with status badges, replay/rerun/❤ buttons |
| **Analytics** | Charts: success rate over time, delegations by agent, cost breakdown, failure types, learned rankings |
| **Compare** | Side-by-side A/B model comparison on same task |
| **Queue** | Scheduled cron tasks + pending queued tasks |
| **Execute** | Task input, model/workflow/from-agent selectors, stream toggle, Execute button |
| **Settings** | 4 sub-tabs: Routing, Control, Notifications, General |

### 7. Settings Sub-tabs

| Sub-tab | Sections |
|---------|----------|
| **Routing** | Provider Priority (drag reorder) + Edit Routes (inline dropdowns) |
| **Control** | Circuit Breaker config + Cooldown Status (live timers) |
| **Notifications** | Telegram (bot token, chat ID, event checkboxes) + Webhooks (Slack/Discord/Email) |
| **General** | Preferences (defaults) + Danger Zone (reset/clear) |

### 8. Keyboard Shortcuts
Bottom status bar + `?` modal. Keys: L Live, O Logs, H History, A Analytics, C Compare, Q Queue, E Execute, S Settings, 1-3 Select task, F7 Project, ⌘K Commands, Esc Close

### 9. Toast Notifications
Fixed top-right panel. Appears on: task completed, task failed/rate limited. Auto-dismiss or manual close.

### 10. Tooltips
Hover info icons (`◎` circle) on all notification settings. Detailed setup instructions for Telegram/Slack/Discord.

## API Endpoints

| Method | Path | Response |
|--------|------|----------|
| GET | `/` | Serves `dashboard.html` |
| GET | `/api/status` | `{agents: [...], active_tasks: [...], cooldowns: [...], metrics: {...}}` |
| GET | `/api/metrics?days=7&agent=opencode` | `{delegations: [...], success_rate: 0.92, ...}` |
| GET | `/api/logs?agent=opencode&level=ERROR&limit=200` | `{entries: [...], metrics: {...}}` |
| GET | `/api/routes` | `[{workflow, task, agent, model, fallback_chain}, ...]` |
| GET | `/api/config` | `{provider_priority, cooldown, routes, preferences}` |
| POST | `/api/config` | Accepts partial config update, returns updated config |
| POST | `/api/exec` | `{task, model, workflow, from_agent, stream}` → `{task_id, status}` |
| POST | `/api/tasks/:id/stop` | `{success: true}` |
| GET | `/api/tasks/:id/output` | `{output: "...", status: "running|done|failed"}` |

## Dependencies

- **Zero new Python dependencies** — stdlib only (`http.server`, `json`, `sqlite3`, `pathlib`)
- **Zero npm/Node.js dependencies** — dashboard HTML is self-contained single file
- **Zero CDN dependencies** — Tailwind CSS compiled into the HTML file (not loaded from CDN)
- **Zero external API calls** — no analytics, no fonts CDN, no image CDN

## Packaging

```bash
pip install delegator           # CLI + Dashboard (default)
pip install delegator[cli]      # CLI only, no dashboard HTML
```

Dashboard is included by default. The `[cli]` extra explicitly excludes it for minimal installs.

## Repo Structure (What Ships)

| Path | Ships in Package? | Purpose |
|------|-------------------|---------|
| `delegator/dashboard/server.py` | ✅ Yes | HTTP server |
| `delegator/dashboard/api.py` | ✅ Yes | API endpoints |
| `delegator/dashboard/templates/dashboard.html` | ✅ Yes | Bundled UI |
| `mockups/dashboard-mockup.html` | ❌ No | Design reference only |
| `docs/specs/*.md` | ❌ No | Design docs only |
| `docs/plans/*.md` | ❌ No | Implementation plans only |

## Testing

- Unit tests for API endpoints using `http.client` or `requests`
- Verify all endpoints return valid JSON
- Verify server binds to 127.0.0.1 only
- Verify dashboard HTML loads without errors
- Verify exec endpoint calls delegator.executor.execute() correctly
