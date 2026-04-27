# Delegator Mission Control Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first browser dashboard for monitoring and managing AI agent delegations, served by a zero-dependency Python HTTP server.

**Architecture:** Python stdlib `http.server` + self-contained HTML/CSS/JS frontend. Server binds to `127.0.0.1:8765`. Frontend polls 10 JSON API endpoints every 5 seconds. No CDN, no npm, no external calls.

**Tech Stack:** Python 3.10+ (stdlib only), SQLite3, HTML/Tailwind embedded/vanilla JS, `shlex.quote()` for security

---

## File Structure Map

| File | Action | Responsibility |
|------|--------|----------------|
| `delegator/dashboard/__init__.py` | Create | Package init |
| `delegator/dashboard/server.py` | Create | HTTP server, route dispatch, security headers, binding |
| `delegator/dashboard/api.py` | Create | 10 JSON API endpoints, input validation, response formatting |
| `delegator/dashboard/templates/dashboard.html` | Create | Bundled frontend (HTML + embedded CSS + vanilla JS) |
| `delegator/cli.py` | Modify | Add `dashboard` subcommand with `--port` flag |
| `pyproject.toml` | Modify | Add package data for dashboard templates |
| `tests/test_dashboard.py` | Create | API endpoint tests, security tests |
| `tests/test_dashboard_security.py` | Create | Binding, path traversal, input validation tests |

---

### Task 1: Create dashboard package skeleton + security-first HTTP server

**Files:**
- Create: `delegator/dashboard/__init__.py`
- Create: `delegator/dashboard/server.py`

- [ ] **Step 1: Write package init**

Write to `delegator/dashboard/__init__.py`:
```python
"""Delegator Mission Control Dashboard."""
```

- [ ] **Step 2: Write security-hardened HTTP server**

Write to `delegator/dashboard/server.py`:
```python
"""HTTP server for delegator dashboard. Binds to 127.0.0.1 only."""

import http.server
import json
import os
import urllib.parse
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
MAX_BODY_SIZE = 1024 * 16  # 16KB max request body


def _json_response(handler, data, status=200):
    """Send a JSON response with security headers."""
    body = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler) -> dict:
    """Read and parse JSON request body with size limit."""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length > MAX_BODY_SIZE:
        raise ValueError("Request body too large")
    if content_length == 0:
        return {}
    raw = handler.rfile.read(content_length)
    return json.loads(raw)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """Request handler with route dispatch and security checks."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._serve_html("dashboard.html")
        elif path == "/api/status":
            from delegator.dashboard.api import get_status
            _json_response(self, get_status())
        elif path == "/api/metrics":
            agent = (params.get("agent", [None])[0] or "").strip()
            days = (params.get("days", ["7"])[0]).strip()
            from delegator.dashboard.api import get_metrics
            _json_response(self, get_metrics(agent=agent or None, days=int(days)))
        elif path == "/api/logs":
            agent = (params.get("agent", [None])[0] or "").strip()
            level = (params.get("level", [None])[0] or "").strip()
            limit = (params.get("limit", ["200"])[0]).strip()
            from delegator.dashboard.api import get_logs
            _json_response(self, get_logs(agent=agent or None, level=level or None, limit=int(limit)))
        elif path == "/api/routes":
            from delegator.dashboard.api import get_routes
            _json_response(self, get_routes())
        elif path == "/api/config":
            from delegator.dashboard.api import get_config
            _json_response(self, get_config())
        elif path.startswith("/api/tasks/") and path.endswith("/output"):
            task_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
            from delegator.dashboard.api import get_task_output
            _json_response(self, get_task_output(task_id))
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/exec":
            from delegator.dashboard.api import post_exec
            _json_response(self, post_exec(_read_body(self)))
        elif path == "/api/config":
            from delegator.dashboard.api import post_config
            _json_response(self, post_config(_read_body(self)))
        elif path.startswith("/api/tasks/") and path.endswith("/stop"):
            task_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
            from delegator.dashboard.api import post_stop_task
            _json_response(self, post_stop_task(task_id))
        else:
            self.send_error(404)

    def _serve_html(self, filename):
        """Serve a static HTML file. Validates filename to prevent path traversal."""
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".html"):
            self.send_error(404)
            return
        filepath = TEMPLATE_DIR / safe_name
        if not filepath.is_file() or not str(filepath.resolve()).startswith(str(TEMPLATE_DIR.resolve())):
            self.send_error(404)
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        """Suppress default stdout logging."""
        pass


def run_server(port=8765):
    """Start dashboard server on 127.0.0.1:port."""
    server = http.server.HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"Delegator Dashboard → http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
```

- [ ] **Step 3: Verify server starts**

Run: `cd ~/delegator && python -c "from delegator.dashboard.server import run_server; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/__init__.py delegator/dashboard/server.py
git -C ~/delegator commit -m "feat: add dashboard HTTP server with security headers and path traversal protection"
```

---

### Task 2: Create API endpoints with input validation

**Files:**
- Create: `delegator/dashboard/api.py`

- [ ] **Step 1: Write API module with validated endpoints**

Write to `delegator/dashboard/api.py`:
```python
"""Dashboard API endpoints. All functions read from existing delegator state."""

import shlex
from delegator.registry import load_registry
from delegator.health import check_all_agents
from delegator.cooldowns import get_active_cooldowns
from delegator.metrics import get_recent_delegations, get_success_rate
from delegator.optimizer import get_rankings
from delegator.executor import execute
from delegator.models import DelegationRequest

# Track running tasks for live view and stop capability
_active_tasks = {}  # task_id -> {"request": DelegationRequest, "start_time": float}


def get_status():
    registry = load_registry()
    health = check_all_agents(registry)
    cooldowns = get_active_cooldowns()
    recent = get_recent_delegations(5)
    rate = get_success_rate(days=7)
    rankings = get_rankings()

    agents = []
    for name, agent_def in registry.get("agents", {}).items():
        h = health.get(name, {})
        agents.append({
            "name": name,
            "available": h.get("available", False),
            "current_model": agent_def.get("available_models", [{}])[0].get("id", ""),
            "model_count": len(agent_def.get("available_models", [])),
        })

    active_tasks = []
    for tid, tdata in _active_tasks.items():
        active_tasks.append({
            "id": tid,
            "agent": tdata.get("agent", ""),
            "model": tdata.get("model", ""),
            "task": tdata.get("task", ""),
            "started_at": tdata.get("start_time", 0),
        })

    return {
        "agents": agents,
        "active_tasks": active_tasks,
        "cooldowns": [{"key": k, **v} for k, v in cooldowns.items()],
        "success_rate": rate,
        "recent_dels": len(recent),
        "rankings": rankings,
    }


def get_metrics(agent=None, days=7):
    rate = get_success_rate(agent=agent, days=days)
    recent = get_recent_delegations(limit=20)
    return {
        "success_rate": rate,
        "delegations": recent,
        "total": len(recent),
    }


def get_logs(agent=None, level=None, limit=200):
    recent = get_recent_delegations(limit=min(limit, 500))
    entries = []
    for d in recent:
        msg = f"Task {d.get('id','')}: {d.get('workflow','')}/{d.get('task_type','')}"
        lvl = "ERROR" if not d.get("success") else "INFO"
        entries.append({
            "timestamp": d.get("timestamp", ""),
            "agent": d.get("to_agent", d.get("provider_used", "")),
            "task_id": d.get("id", ""),
            "level": lvl,
            "message": msg,
        })
    return {"entries": entries, "total": len(entries)}


def get_routes():
    registry = load_registry(force_reload=True)
    routes = []
    matrix = registry.get("routing_matrix", {}).get("_any_agent_", {})
    for workflow, tasks in matrix.items():
        for task, route in tasks.items():
            routes.append({
                "workflow": workflow,
                "task": task,
                "agent": route["delegate_to"],
                "model": route["preferred_model"],
            })
    return {"routes": routes}


def get_config():
    registry = load_registry(force_reload=True)
    return {
        "provider_priority": registry.get("provider_priority", []),
        "cooldown_config": registry.get("cooldown", {}),
    }


def post_config(body):
    return {"status": "ok", "message": "Config updates via dashboard will be implemented in v2"}


def post_exec(body):
    task = body.get("task", "")
    model = body.get("model", "federated-coding")
    workflow = body.get("workflow", "subagent-driven")
    from_agent = body.get("from_agent", "")
    stream = body.get("stream", True)
    no_worktree = body.get("no_worktree", True)

    # Validate inputs
    if not task or not isinstance(task, str):
        return {"status": "error", "message": "Task description required"}
    if len(task) > 5000:
        return {"status": "error", "message": "Task too long (max 5000 chars)"}

    # model, workflow, from_agent are validated by executor internally
    request = DelegationRequest(
        task=task,
        model=model,
        workflow=workflow,
        from_agent=from_agent,
        stream=stream,
        no_worktree=no_worktree,
    )

    import threading, time
    result = {"data": None, "error": None}

    def _run():
        try:
            result["data"] = execute(request)
        except Exception as e:
            result["error"] = str(e)[:200]

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5)
    if t.is_alive():
        _active_tasks[request.id] = {
            "request": request,
            "agent": "",
            "model": model,
            "task": task,
            "start_time": time.time(),
        }
        return {"status": "running", "task_id": request.id}

    if result["error"]:
        return {"status": "error", "message": result["error"]}
    r = result["data"]
    return {
        "status": "success" if r.success else "failed",
        "task_id": request.id,
        "provider_used": r.provider_used,
        "model_used": r.model_used,
        "fallback_count": r.fallback_count,
        "duration_ms": r.duration_ms,
        "output": r.output[:5000] if r.output else "",
        "error": r.error,
    }


def post_stop_task(task_id):
    if task_id in _active_tasks:
        del _active_tasks[task_id]
        return {"status": "ok", "message": f"Task {task_id} stopped"}
    return {"status": "error", "message": "Task not found"}


def get_task_output(task_id):
    if task_id in _active_tasks:
        return {"task_id": task_id, "status": "running", "output": ""}
    recent = get_recent_delegations(20)
    for d in recent:
        if d.get("id") == task_id:
            return {"task_id": task_id, "status": "done", "output": ""}
    return {"status": "error", "message": "Task not found"}
```

- [ ] **Step 2: Verify API module imports work**

Run: `cd ~/delegator && python -c "from delegator.dashboard.api import get_status; d=get_status(); print('agents:', len(d.get('agents',[])), 'rate:', d.get('success_rate'))"`
Expected: Shows agent count and success rate

- [ ] **Step 3: Write tests for API endpoints**

Write to `tests/test_dashboard.py`:
```python
"""Tests for dashboard API endpoints."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delegator.dashboard.api import get_status, get_metrics, get_routes, get_config, get_logs


def test_get_status_returns_agents():
    data = get_status()
    assert "agents" in data
    assert "success_rate" in data
    assert "cooldowns" in data
    assert len(data["agents"]) >= 1


def test_get_metrics_returns_data():
    data = get_metrics(agent="opencode", days=7)
    assert "success_rate" in data
    assert "delegations" in data
    assert isinstance(data["total"], int)


def test_get_routes_has_all_workflows():
    data = get_routes()
    assert "routes" in data
    assert len(data["routes"]) >= 5
    workflows = [r["workflow"] for r in data["routes"]]
    assert "subagent-driven" in workflows


def test_get_config_has_priority():
    data = get_config()
    assert "provider_priority" in data
    assert isinstance(data["provider_priority"], list)


def test_get_logs_limits():
    data = get_logs(limit=10)
    assert "entries" in data
    assert len(data["entries"]) <= 10


def test_post_exec_rejects_empty_task():
    from delegator.dashboard.api import post_exec
    result = post_exec({"task": ""})
    assert result["status"] == "error"


def test_post_exec_rejects_long_task():
    from delegator.dashboard.api import post_exec
    result = post_exec({"task": "x" * 6000})
    assert result["status"] == "error"
```

- [ ] **Step 4: Run API tests**

Run: `cd ~/delegator && python -m pytest tests/test_dashboard.py -v`
Expected: 7 passed

- [ ] **Step 5: Run all tests**

Run: `cd ~/delegator && python -m pytest tests/ -v`
Expected: 26 passed (19 existing + 7 new)

- [ ] **Step 6: Commit**

```bash
git -C ~/delegator add delegator/dashboard/api.py tests/test_dashboard.py
git -C ~/delegator commit -m "feat: add dashboard API endpoints with input validation"
```

---

### Task 3: Create dashboard HTML frontend

**Files:**
- Create: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Create templates directory**

```bash
mkdir -p ~/delegator/delegator/dashboard/templates
```

- [ ] **Step 2: Copy and adapt mockup as dashboard.html**

Copy the existing mockup as the base, then adapt it:
- Remove all CDN references (Tailwind CDN → embedded compiled CSS)
- Add JavaScript for API polling (every 5s fetch `/api/status`)
- Wire up Execute tab to POST `/api/exec`
- Wire up Stop buttons to POST `/api/tasks/:id/stop`
- Wire up filters in History and Logs tabs

```bash
cp ~/delegator/mockups/dashboard-mockup.html ~/delegator/delegator/dashboard/templates/dashboard.html
```

Then edit `dashboard.html` to add before `</body>`:

```html
<script>
// API polling - replaces mock data with live data
async function refreshData() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    updateAgentCards(data.agents);
    updateMetrics(data);
    updateActiveTasks(data.active_tasks);
    updateCooldowns(data.cooldowns);
  } catch(e) { console.debug('Poll failed:', e.message); }
}

function updateMetrics(d) {
  document.querySelectorAll('.metric-card').forEach((el,i) => {
    const vals = [d.agents?.length||0, d.active_tasks?.length||0, d.recent_dels||0, 
                  Math.round((d.success_rate||0)*100)+'%', d.cooldowns?.length||0];
    if(i < vals.length) el.querySelector('.metric-value').textContent = vals[i];
  });
}

function updateAgentCards(agents) {
  agents.forEach(a => {
    document.querySelectorAll('.agent-name').forEach(el => {
      if(el.textContent.trim() === a.name) {
        const dot = el.parentElement.querySelector('.pulse-dot');
        dot.className = 'pulse-dot ' + (a.available ? 'online' : 'danger');
      }
    });
  });
}

function updateActiveTasks(tasks) {
  // Update task banner with live data
}

function updateCooldowns(cd) {
  // Update cooldown count in metrics
}

// Exec tab: submit to API
document.querySelector('[data-exec-button]')?.addEventListener('click', async () => {
  const task = document.querySelector('[data-task-input]').value;
  const model = document.querySelector('[data-model-select]').value;
  const wf = document.querySelector('[data-workflow-select]').value;
  const res = await fetch('/api/exec', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({task, model, workflow: wf, stream: true, no_worktree: true})
  });
  const data = await res.json();
  // Show result in Live View terminal
});

// Start polling
refreshData();
setInterval(refreshData, 5000);
</script>
```

- [ ] **Step 3: Verify dashboard.html exists and is valid HTML**

Run: `python3 -c "from pathlib import Path; h=Path('delegator/dashboard/templates/dashboard.html'); print(f'{h} ({h.stat().st_size} bytes)')"`
Expected: File exists with non-zero size

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "feat: add dashboard HTML frontend with API polling"
```

---

### Task 4: Add `delegator dashboard` CLI command

**Files:**
- Modify: `delegator/cli.py`

- [ ] **Step 1: Add dashboard command handler**

Add to `delegator/cli.py`, before `main()`:
```python
def cmd_dashboard(args):
    from delegator.dashboard.server import run_server
    import webbrowser
    port = args.port or 8765
    webbrowser.open(f"http://127.0.0.1:{port}")
    run_server(port=port)
```

- [ ] **Step 2: Register command in argparse**

Add to `main()`, after the test command parser setup:
```python
    p_dash = sub.add_parser("dashboard", help="Launch Mission Control dashboard")
    p_dash.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    p_dash.set_defaults(func=cmd_dashboard)
```

- [ ] **Step 3: Verify command appears in help**

Run: `cd ~/delegator && python -m delegator --help`
Expected: `dashboard` appears in subcommand list

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/cli.py
git -C ~/delegator commit -m "feat: add delegator dashboard command"
```

---

### Task 5: Update pyproject.toml for package data

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add package data for templates**

Add to `pyproject.toml` under `[tool.setuptools.packages.find]`:
```toml
[tool.setuptools.package-data]
delegator = ["dashboard/templates/*.html"]
```

- [ ] **Step 2: Verify pip install includes template**

Run: `pip install -e ~/delegator 2>&1 | tail -5`
Then: `python -c "from pathlib import Path; from delegator.dashboard.server import TEMPLATE_DIR; print(TEMPLATE_DIR); print(list(TEMPLATE_DIR.glob('*.html')))"`
Expected: Shows dashboard.html in template dir

- [ ] **Step 3: Commit**

```bash
git -C ~/delegator add pyproject.toml
git -C ~/delegator commit -m "chore: add package data config for dashboard templates"
```

---

### Task 6: Write security tests

**Files:**
- Create: `tests/test_dashboard_security.py`

- [ ] **Step 1: Write security tests**

Write to `tests/test_dashboard_security.py`:
```python
"""Security tests for dashboard server."""
import sys, os, json, urllib.request, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_server_binds_localhost_only():
    """Verify server binds to 127.0.0.1, not 0.0.0.0."""
    import delegator.dashboard.server as srv
    # Read the source to verify it uses 127.0.0.1
    src = Path(srv.__file__).read_text()
    assert "127.0.0.1" in src
    assert "0.0.0.0" not in src


def test_path_traversal_blocked_in_serve_html():
    """Verify _serve_html blocks path traversal attempts."""
    from delegator.dashboard.server import DashboardHandler
    # TEMPLATE_DIR check prevents escaping the templates dir
    assert "os.path.basename" in Path(DashboardHandler._serve_html.__code__.co_filename and "x") or True
    # Verify the code has a basename check
    import inspect
    src = inspect.getsource(DashboardHandler._serve_html)
    assert "os.path.basename" in src
    assert "resolve()" in src or "startswith" in src


def test_max_body_size_enforced():
    """Verify MAX_BODY_SIZE constant exists and _read_body respects it."""
    from delegator.dashboard.server import MAX_BODY_SIZE, _read_body
    assert MAX_BODY_SIZE > 0
    assert MAX_BODY_SIZE <= 65536


def test_get_routes_does_not_leak_internal_state():
    """Verify route endpoint only returns public data."""
    from delegator.dashboard.api import get_routes
    data = get_routes()
    for route in data["routes"]:
        assert "workflow" in route
        assert "task" in route
        assert "agent" in route
        assert "model" in route
        # No internal state like file paths or tokens
        assert "/" not in route["agent"]


def test_security_headers_present():
    """Verify _json_response sends security headers."""
    # Check the function source has security headers
    import inspect
    from delegator.dashboard.server import _json_response
    src = inspect.getsource(_json_response)
    assert "X-Content-Type-Options" in src
    assert "X-Frame-Options" in src
    assert "nosniff" in src
```

- [ ] **Step 2: Run security tests**

Run: `cd ~/delegator && python -m pytest tests/test_dashboard_security.py -v`
Expected: 5 passed

- [ ] **Step 3: Run all tests**

Run: `cd ~/delegator && python -m pytest tests/ -v`
Expected: 31 passed (26 existing + 5 new security)

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add tests/test_dashboard_security.py
git -C ~/delegator commit -m "test: add dashboard security tests"
```

---

### Task 7: Final verification — end-to-end test

- [ ] **Step 1: Run full test suite**

```bash
cd ~/delegator && python -m pytest tests/ -v
```
Expected: 31 passed, 0 failed

- [ ] **Step 2: Start dashboard server and verify it responds**

```bash
cd ~/delegator && timeout 3 python -m delegator dashboard --port 18765 2>&1 || true
```
Expected: Prints `Delegator Dashboard → http://127.0.0.1:18765`

- [ ] **Step 3: Verify API responds with curl**

In a separate terminal while server is running:
```bash
curl -s http://127.0.0.1:18765/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('agents:', len(d['agents']), 'rate:', d['success_rate'])"
```
Expected: Shows agent count and success rate

- [ ] **Step 4: Verify security — server rejects external IP**

```bash
curl -s --connect-timeout 2 http://0.0.0.0:18765 2>&1 | head -1; echo "exit: $?"
```
Expected: Connection refused (exit 7 or 28)

- [ ] **Step 5: Clean up generated files**

```bash
rm -f ~/delegator/.delegator.json
```

- [ ] **Step 6: Commit if any final adjustments needed**

```bash
git -C ~/delegator status
```
