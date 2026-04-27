# Delegator Mission Control — Rebuild Specification

**Created:** 2026-04-28
**Backup:** `dashboard/templates/dashboard.html.backup` (105KB)
**Status:** Rebuilding from scratch based on lessons learned

## Why Rebuild

After 6 iterations of patching a mockup, the current dashboard has:
- 875 lines, ~200 lines of dead/hardcoded mock HTML
- Functions defined multiple times (old stubs + new versions)
- CSS selectors that don't match because classes changed
- Unbalanced braces that silently broke all JS for hours

The backend APIs are solid (34 tests pass). The frontend needs clean foundations.

## Requirements (from original spec + user feedback)

### Core Principles
1. Local-first — all data stays on 127.0.0.1, no CDN, no external calls
2. API-driven — every data point comes from a backend endpoint, zero hardcoded mock data
3. Real-time — polling-based auto-refresh for all tabs (metrics=5s, logs=8s, live=4s)
4. Keyboard-driven — all tabs/major actions have shortcuts (16 keys)
5. Dark OLED theme — #020617 background, #22C55E accent, JetBrains Mono font

### Tabs (must all load live data on switch + auto-poll)
1. **Live View** — streaming terminal showing selected task output
2. **Logs** — delegation log entries from metrics DB, filterable by agent/level, searchable, exportable
3. **History** — delegation table from metrics DB, filterable, exportable, viewable (shows real task details), ❤ feedback
4. **Analytics** — 7d success rate chart, delegations by agent, cost breakdown, failure types, learned rankings, PDF/CSV export
5. **Compare** — A/B model comparison with model selector dropdowns, run button, side-by-side live outputs
6. **Queue** — scheduled tasks (cron-based) + pending queue with Start/Run/Add buttons
7. **Execute** — task input, model select, workflow select, Stream/No worktree toggles, Execute button
8. **Settings** — 4 sub-tabs: Routing, Control, Notifications, General

### Settings Sub-tabs
- **Routing** — drag-to-reorder provider priority, edit route dropdowns (savable)
- **Control** — circuit breaker config (threshold/base/max cooldown, worktree TTL), live cooldown status, reset/auto-heal buttons
- **Notifications** — Telegram (bot token, chat ID, event checkboxes, save config, send test), Webhooks (Slack/Discord/Email, same capabilities)
- **General** — preferences (default model/workflow/refresh interval), danger zone (reset cooldowns, clear history, reset rankings)

### Non-Tab Elements
- **Header** — project switcher (discovered from filesystem), auto-heal button, theme toggle
- **Metrics row** — 8 live stat cards
- **Active tasks banner** — collapsible, shows running tasks with progress bars + timers + stop buttons
- **Alert bar** — shows only when cooldowns/issues exist
- **Agent cards** (left rail) — 5 cards with health dots, current model, success rate bars, delegation count, cost, clickable modals with per-model stats
- **Toast notifications** — appear on task start/complete/fail
- **Bottom status bar** — keyboard shortcut hints
- **Keyboard shortcuts modal** — `?` opens full reference
- **Modal: Agent details** — per-model stats from API

### Backend API Endpoints (already working, keep as-is)
- `GET /api/status` — agents, tasks, cooldowns, metrics, project
- `GET /api/routes` — routing matrix
- `GET /api/config` — provider priority, cooldown config, notifications, queues
- `POST /api/config` — save notifications, auto-heal, clear history, add queue, start queued, reset rankings
- `GET /api/projects` — discovered projects
- `POST /api/projects` — switch active project
- `GET /api/metrics?days=&agent=` — delegation history
- `GET /api/logs?limit=` — log entries
- `POST /api/exec` — execute delegation
- `GET /api/tasks/:id/output` — task live output
- `POST /api/tasks/:id/stop` — stop running task
- `POST /api/compare` — A/B model comparison
- `GET /api/agents/:name` — per-agent model stats

### User Feedback — Non-Negotiable Requirements
1. Everything must show real data, never mock/fake/dummy
2. All buttons must do something real, never alert() placeholders
3. Agent cards must all be clickable
4. Compare must have model selectors
5. Filter dropdowns must actually filter
6. Export buttons must generate real files
7. Settings must persist
8. History View must show real task details
9. Logs must load real data on init, auto-refresh
10. Analytics charts must use real data with tooltips
11. Provider priority must be draggable
12. Telegram instructions must be accurate
13. No fake placeholder values in input fields
14. `Cmd+K` must do something useful
15. No dead/hidden elements

## Architecture

```
dashboard.html (target: ~300 lines, zero mock data)
├── <style> — embedded CSS, dark OLED theme
├── <body> — minimal structural HTML (containers, tabs, selects)
└── <script>
    ├── INIT: call refreshAll() + loadHistory() + loadRoutes() + loadLogs()
    ├── REFRESH: setInterval for metrics(5s), logs(8s), live(4s)
    ├── TEMPLATES: render*() functions that generate HTML from API data
    ├── ACTIONS: execTask, stopTask, runCompare, addPending, etc.
    └── EVENTS: keyboard shortcuts, click delegation, tab switching
```

### Key Design Decision: Render from API, not from static HTML

Every tab's content is EMPTY in the HTML. On page load and tab switch, a `render*()` function:
1. Fetches data from the API
2. Builds innerHTML from the data using template literals
3. Attaches any needed event handlers inline

This eliminates all mock data and ensures data freshness.

### What We Keep From Current
- All of `delegator/dashboard/api.py` (solid backend)
- All of `delegator/dashboard/server.py` (solid server)
- `delegator/dashboard/__init__.py`
- All tests (34 passing)
- `design system` (colors, fonts, spacing)

### What We Discard
- `dashboard.html` (backed up as `.backup`)
- All mock data, placeholder values, dead code
- Duplicate function definitions
- Broken CSS selectors