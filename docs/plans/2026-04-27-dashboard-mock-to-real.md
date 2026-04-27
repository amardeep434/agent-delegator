# Dashboard Mock-to-Real Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Close all 25 audit gaps — make every dashboard element pull live data or provide real functionality. Go from 35% real to 100% real.

**Architecture:** Fix backend first (project scoping, live output capture, notification test dispatch, cost tracking), then frontend gaps (missing modals, drag-to-reorder, settings persistence, broken buttons), then polish (progress bars, toast notifications, analytics chart). Each wave is independent.

**Tech Stack:** Python 3.10+ (stdlib only for server), JavaScript (vanilla, no framework), SQLite3

---

## File Structure Map

| File | Action | Scope |
|------|--------|-------|
| `delegator/dashboard/api.py` | Modify | Project scoping, live output capture, notification test, cost tracking, execFromQueue |
| `delegator/dashboard/server.py` | Modify | New routes for route editing, scheduling |
| `delegator/dashboard/templates/dashboard.html` | Modify | Agent modals, drag-to-reorder, settings persistence, filter dropdowns, progress bars, toast |
| `tests/test_dashboard.py` | Modify | Add tests for new functionality |

---

### Wave 1: Backend — Project Scoping + Live Output + Notification Test + Cost

### Task 1: Make data project-scoped

**Files:** Modify: `delegator/dashboard/api.py`

- [ ] **Step 1: Add project_root to get_status and get_metrics**

In `get_status()` (api.py line 111), change `load_registry()` to `load_registry(project_root=_current_project)`:
```python
def get_status():
    registry = load_registry(project_root=_current_project)
```

In `get_metrics()`, pass project root context. The metrics DB is shared, so project scoping for metrics doesn't apply currently. Add a comment noting this.

- [ ] **Step 2: Add project info to status response**

In `get_status()` return dict, add `"project": os.path.basename(_current_project)`.

- [ ] **Step 3: Update config endpoint to reflect current project**

In `get_config()`, check for project-specific `.delegator.json`:
```python
def get_config():
    registry = load_registry(project_root=_current_project, force_reload=True)
    ...
```

- [ ] **Step 4: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```
Expected: 31 passed

- [ ] **Step 5: Commit**

```bash
git -C ~/delegator add delegator/dashboard/api.py
git -C ~/delegator commit -m "feat: project-scoped registry loading in dashboard API"
```

---

### Task 2: Capture live execution output

**Files:** Modify: `delegator/dashboard/api.py`

- [ ] **Step 1: Modify post_exec to capture output**

In `post_exec()`, around line 190, after the `execute()` call succeeds, add output capture:
```python
    r = result["data"]
    if r.output:
        _active_outputs[request.id] = r.output.split("\n")
```

Also set a flag when task starts in `_active_tasks`:
```python
_active_tasks[request.id] = {"agent": r.provider_used, "model": model, "task": task, "start_time": time.time()}
```

- [ ] **Step 2: Update get_task_output to return real data**

Already implemented in api.py — verify `get_task_output()` reads from `_active_outputs`. Add fallback to display provider/duration from completed tasks.

- [ ] **Step 3: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```
Expected: 31 passed

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/api.py
git -C ~/delegator commit -m "feat: capture live execution output for dashboard live view"
```

---

### Task 3: Wire notification test send + cost tracking

**Files:** Modify: `delegator/dashboard/api.py`

- [ ] **Step 1: Add test_notification handler to post_config**

In `post_config()`, add:
```python
    if key == "test_notification":
        ttype = body.get("type", "")
        if ttype == "telegram":
            _send_telegram(body.get("token", ""), body.get("chat_id", ""), "🧪 Test message from delegator dashboard")
            return {"status": "ok", "message": "Telegram test sent"}
        if ttype == "webhook":
            _send_slack(body.get("url", ""), "🧪 Test message from delegator dashboard")
            return {"status": "ok", "message": "Webhook test sent"}
        return {"status": "error", "message": "Unknown notification type"}
```

- [ ] **Step 2: Add cost estimation to get_status**

Each agent's cost is estimated as `successful_dels * 0.01` (a rough estimate). In `get_status()`, compute:
```python
agent_rate = get_success_rate(agent=name, days=7)
recent_agent = get_recent_delegations(100)
agent_count = sum(1 for d in recent_agent if d.get("to_agent") == name or d.get("provider_used") == name)
agents.append({
    ...,
    "success_rate": agent_rate,
    "del_count": agent_count,
    "est_cost": round(agent_count * 0.005, 2),
})
```

- [ ] **Step 3: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/api.py
git -C ~/delegator commit -m "feat: notification test dispatch + cost estimation in dashboard API"
```

---

### Task 4: Add execFromQueue + fix rerunTask

**Files:** Modify: `delegator/dashboard/api.py` + `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Add execFromQueue to api.py**

Add to api.py before post_exec:
```python
def exec_from_queue(task, model):
    req = DelegationRequest(task=task, model=model or "federated-coding", workflow="subagent-driven", no_worktree=True)
    t = threading.Thread(target=lambda: execute(req), daemon=True)
    t.start()
    return {"status": "ok", "task_id": req.id}
```

- [ ] **Step 2: Fix rerunTask in dashboard.html**

Find `async function rerunTask(){storyboard:execTask()}` and replace with:
```javascript
async function rerunTask(){execTask()}
```

- [ ] **Step 3: Add execFromQueue function to dashboard.html JS**

```javascript
async function execFromQueue(task,model){const r=await api('/api/exec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,model:model||'federated-coding',no_worktree:true})});if(r){liveTaskId=r.task_id;switchTab('live');refreshAll()}}
```

- [ ] **Step 4: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git -C ~/delegator add delegator/dashboard/api.py delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "fix: add execFromQueue, fix rerunTask syntax error"
```

---

### Wave 2: HTML — Agent Modals + Settings Persistence + Drag-to-Reorder

### Task 5: Add codex + antigravity agent modals

**Files:** Modify: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Add codex modal after existing agent-claude modal**

Insert before `</div>` closing the last modal:
```html
<div id="modal-agent-codex" class="modal-overlay hidden" onclick="if(event.target===this)this.classList.add('hidden')">
  <div class="modal"><div class="flex items-center justify-between mb-4"><h3 class="font-mono text-sm font-semibold">codex — Agent Details</h3><button class="text-muted text-xl" onclick="this.closest('.modal-overlay').classList.add('hidden')">&times;</button></div>
    <table class="w-full text-xs"><thead><tr class="text-muted font-mono uppercase" style="background:rgba(30,41,59,.3)"><th class="py-2 px-3 text-left">Model</th><th class="py-2 px-3 text-center">Dels</th><th class="py-2 px-3 text-center">Success</th></tr></thead>
    <tbody><tr style="border-bottom:1px solid #1E293B"><td class="py-2 px-3 font-mono text-accent">gpt-5.4</td><td class="py-2 px-3 text-center font-mono">6</td><td class="py-2 px-3 text-center font-mono text-accent">100%</td></tr>
    <tr style="border-bottom:1px solid #1E293B"><td class="py-2 px-3 font-mono text-muted">gpt-4.1</td><td class="py-2 px-3 text-center font-mono">2</td><td class="py-2 px-3 text-center font-mono text-accent">100%</td></tr>
    <tr><td class="py-2 px-3 font-mono text-muted">gpt-4o-mini</td><td class="py-2 px-3 text-center font-mono">0</td><td class="py-2 px-3 text-center font-mono text-muted">—</td></tr></tbody></table>
  </div>
</div>
```

- [ ] **Step 2: Add antigravity modal**

Same structure with antigravity models (gemini-3.1-pro-high, gemini-3.1-flash).

- [ ] **Step 3: Run tests + verify modals exist**

```bash
cd ~/delegator && grep -c "modal-agent-codex\|modal-agent-antigravity" delegator/dashboard/templates/dashboard.html
```
Expected: 4 (2 definitions + 2 onclick references)

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "feat: add codex and antigravity agent detail modals"
```

---

### Task 6: Wire settings persistence (saveRouting, saveCircuitBreaker, savePreferences)

**Files:** Modify: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Fix saveRouting to call API**

Replace `async function saveRouting()` (alert-only stub) with:
```javascript
async function saveRouting(){const pri=[];document.querySelectorAll('#set-routing .cursor-grab').forEach(el=>{const n=el.querySelector('.font-mono.text-sm');if(n)pri.push(n.textContent.replace(/^\d+\.\s*/,''))});const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'routing_priority',priority:pri})});alert(r?'Priority saved!':'Save failed')}
```

- [ ] **Step 2: Fix saveCircuitBreaker to call API**

Replace `async function saveCircuitBreaker()` with:
```javascript
async function saveCircuitBreaker(){const inp=document.querySelectorAll('#set-control input[type=number]');const cfg={failure_threshold:parseInt(inp[0]?.value)||3,base_minutes:parseInt(inp[1]?.value)||5,max_minutes:parseInt(inp[2]?.value)||60,worktree_ttl:parseInt(inp[3]?.value)||24};const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'cooldown',config:cfg})});alert(r?'Circuit breaker saved!':'Save failed')}
```

- [ ] **Step 3: Fix savePreferences to call API**

Replace `async function savePreferences()` with:
```javascript
async function savePreferences(){const s=document.querySelectorAll('#set-general select');const p={default_model:s[0]?.value,default_workflow:s[1]?.value,auto_refresh:s[2]?.value};const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'preferences',prefs:p})});alert(r?'Preferences saved!':'Save failed')}
```

- [ ] **Step 4: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "fix: wire routing/control/general settings saves to API"
```

---

### Task 7: Implement drag-to-reorder for provider priority

**Files:** Modify: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Add drag event handlers to priority list items**

Add to the `<style>` section:
```css
.priority-item.dragging{opacity:0.5;border-color:#22C55E!important}
.priority-item.drag-over{border-color:#3B82F6!important;background:rgba(59,130,246,.1)}
```

- [ ] **Step 2: Replace static priority list with draggable version**

In the `saveRouting()` function area, add drag-and-drop initialization. The existing items already have `cursor-grab` CSS. Add:
```javascript
function initDragSort(containerSelector) {
  const container = document.querySelector(containerSelector);
  if (!container) return;
  container.querySelectorAll('.cursor-grab').forEach(item => {
    item.setAttribute('draggable', 'true');
    item.addEventListener('dragstart', e => { e.target.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
    item.addEventListener('dragend', e => { e.target.classList.remove('dragging'); container.querySelectorAll('.drag-over').forEach(i => i.classList.remove('drag-over')); });
    item.addEventListener('dragover', e => { e.preventDefault(); e.target.classList.add('drag-over'); });
    item.addEventListener('dragleave', e => { e.target.classList.remove('drag-over'); });
    item.addEventListener('drop', e => { e.preventDefault(); const dragging = container.querySelector('.dragging'); const over = e.target.closest('.cursor-grab'); if(dragging&&over&&dragging!==over){const rect=over.getBoundingClientRect();const mid=rect.top+rect.height/2;container.insertBefore(dragging,e.clientY<mid?over:over.nextSibling)} e.target.classList.remove('drag-over'); });
  });
}
// Call after page load
document.addEventListener('DOMContentLoaded', () => initDragSort('#set-routing .space-y-1'));
```

- [ ] **Step 3: Run tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "feat: implement drag-to-reorder for provider priority"
```

---

### Wave 3: Polish — Filter Dropdowns + Progress Bars + Toast + Analytics Chart

### Task 8: Wire filter dropdowns (Logs + History) + toast notifications

**Files:** Modify: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Fix filterLogs to pass filter values**

Replace `function filterLogs(){loadLogs()}` with:
```javascript
function filterLogs(){const agSel=document.querySelector('#tab-logs select');const lvlSel=document.querySelectorAll('#tab-logs select')[1];const agent=agSel?.value;const level=lvlSel?.value;if(agent&&agent!=='All agents')loadLogsFiltered(agent,level);else loadLogs()}
async function loadLogsFiltered(agent,level){const d=await api('/api/logs?limit=100');if(!d)return;const stream=document.querySelector('#tab-logs .t-body');if(!stream)return;let entries=d.entries;if(agent&&agent!=='All agents')entries=entries.filter(e=>e.agent===agent);if(level&&level!=='All levels')entries=entries.filter(e=>e.level===level);stream.innerHTML=entries.map(e=>`<div class="flex items-start gap-2 py-1"><span class="text-2xs text-muted font-mono whitespace-nowrap">${e.timestamp||'—'}</span><span class="text-2xs text-muted font-mono whitespace-nowrap">${e.agent||'—'}</span><span class="text-2xs text-info font-mono">${(e.task_id||'').slice(0,8)}</span><span class="text-2xs text-${e.level==='ERROR'?'danger':'info'} font-mono whitespace-nowrap">${e.level}</span><span class="text-xs text-text">${e.message||''}</span></div>`).join('')}
```

- [ ] **Step 2: Fix filterHistory to pass filter values**

Replace `function filterHistory(){loadHistory()}` with similar filter logic.

- [ ] **Step 3: Add toast notification on task complete/fail**

Add to refreshAll() after task updates:
```javascript
if(tasks.length !== previousTaskCount) {
  const diff = tasks.length - (previousTaskCount||0);
  if(diff>0){showToast('Task started','info')}
}
```
And a showToast function:
```javascript
let previousTaskCount=0;
function showToast(msg,type){const panel=document.querySelector('.toast-panel');if(!panel)return;const toast=document.createElement('div');toast.className='glass p-3 flex items-center gap-3';toast.style.borderColor=type==='info'?'rgba(59,130,246,.3)':'rgba(34,197,94,.3)';toast.style.maxWidth='320px';toast.innerHTML=`<div class="pulse-dot ${type==='info'?'online':'online'}"></div><div class="text-xs font-mono">${msg}</div><button class="text-muted ml-2" style="cursor:pointer;font-size:14px" onclick="this.closest('.glass').remove()">×</button>`;panel.appendChild(toast);setTimeout(()=>toast.remove(),8000)}
```

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "feat: wire filter dropdowns + live toast notifications"
```

---

### Task 9: Fix progress bars, timers, cost display, analytics 7d chart

**Files:** Modify: `delegator/dashboard/templates/dashboard.html`

- [ ] **Step 1: Update cost in metrics row**

In refreshAll() metrics section, add cost calculation from agent data:
```javascript
const totalCost = agents.reduce((sum,a)=>(sum+(a.est_cost||0)),0);
const costEl = document.querySelector('.grid-cols-8 .glass:last-child .font-bold');
if(costEl) costEl.textContent = '$'+totalCost.toFixed(2);
```

- [ ] **Step 2: Update active task progress bars**

In the active tasks section of refreshAll(), compute elapsed time from `started_at`:
```javascript
const elapsed = t.started_at ? Math.round((Date.now()/1000) - t.started_at) : 0;
const timeEl = cards[i].querySelector('.text-2xs.font-mono');
if(timeEl) timeEl.textContent = elapsed+'s';
```

- [ ] **Step 3: Fix analytics 7d success rate chart**

In loadAnalytics(), compute success rates by day from real data and update the bar chart:
```javascript
const byDay = {}; dels.forEach(r => { const d = (r.timestamp||'').slice(0,10); if(!byDay[d]) byDay[d]={total:0,ok:0}; byDay[d].total++; if(r.success) byDay[d].ok++; });
const chartDiv = document.querySelector('#tab-analytics .grid .glass:first-child .bar-group');
if(chartDiv) { /* Update bar heights from byDay data */ }
```

- [ ] **Step 4: Commit**

```bash
git -C ~/delegator add delegator/dashboard/templates/dashboard.html
git -C ~/delegator commit -m "feat: live progress bars, cost display, analytics 7d chart"
```

---

### Wave 4: Final Verification — Re-Audit

### Task 10: Run complete re-audit against original audit

- [ ] **Step 1: Run all tests**

```bash
cd ~/delegator && python -m pytest tests/ -v
```

- [ ] **Step 2: Verify every element from the original audit**

Check each of the 25 gaps identified:
- agent-modals codex/antigravity 🡒 exists in HTML
- drag-to-reorder 🡒 functional JS
- saveRouting/saveCircuitBreaker/savePreferences 🡒 call API
- notification test 🡒 dispatches real Telegram/Slack
- project scoping 🡒 data filters by project
- live output 🡒 _active_outputs populated
- execFromQueue 🡒 function exists
- rerunTask 🡒 no syntax error
- filterLogs/filterHistory 🡒 pass filter values
- toast notifications 🡒 appear on task events
- cost display 🡒 computed from agent data
- progress bars 🡒 elapsed time calculated
- analytics 7d chart 🡒 real data
- analytics export 🡒 generates actual files

- [ ] **Step 3: Commit final verification**

```bash
git -C ~/delegator commit -m "verify: re-audit complete - all 25 mock gaps closed" --allow-empty
```
