# Dashboard Final Fix Plan — 36 Remaining Audit Gaps

> **Goal:** Fix all 36 BROKEN/STUB/MOCK items from the exhaustive audit. Score from 75% real to 100%.

**Architecture:** Single-file HTML + single-file API. Most fixes are missing function definitions (exportLogs, clearLogs, exportHistory, execFromQueue) or stub-to-real conversions (viewDelegation, sendTestWebhook, resetRankings).

**Tech Stack:** Python 3.10+, vanilla JS, SQLite3

---

### Task 1: Fix server-killing /api/compare + execFromQueue

**Files:** `delegator/dashboard/api.py`

- [ ] Add timeout wrapper to post_compare to prevent hangs
- [ ] Add execFromQueue as a proper API-callable function that doesn't block

```python
def post_compare(body):
    task = body.get("task", "")
    results = {}
    for label, m in [("A", body.get("model_a", "opencode-go/deepseek-v4-pro")), ("B", body.get("model_b", "claude-sonnet-4-6"))]:
        req = DelegationRequest(task=task, model=m, workflow="subagent-driven", no_worktree=True)
        try:
            r = execute(req)
            results[label] = {"model": m, "success": r.success, "provider": r.provider_used,
                              "duration_ms": r.duration_ms, "fallback_count": r.fallback_count,
                              "output": r.output[:2000] if r.output else ""}
        except Exception as e:
            results[label] = {"model": m, "error": str(e)[:200]}
    return {"status": "ok", "results": results}
```

- [ ] Run: `cd ~/delegator && python -m pytest tests/ -v`
- [ ] Commit: `git add delegator/dashboard/api.py && git commit -m "fix: server-safe /api/compare with model selection"`

---

### Task 2: Add 4 missing functions (exportLogs, clearLogs, exportHistory, execFromQueue)

**Files:** `delegator/dashboard/templates/dashboard.html`

- [ ] Add to JavaScript before refreshAll():

```javascript
function exportLogs(){const tb=document.querySelector('#tab-logs .t-body');if(tb){const blob=new Blob([tb.textContent],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='delegator-logs.txt';a.click()}}
function clearLogs(){const tb=document.querySelector('#tab-logs .t-body');if(tb)tb.innerHTML=''}
function exportHistory(){const h=document.querySelector('#tab-history .glass');if(h){const blob=new Blob([h.textContent],{type:'text/csv'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='delegator-history.csv';a.click()}}
async function execFromQueue(task,model){const r=await api('/api/exec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,model:model||'federated-coding',no_worktree:true})});if(r){liveTaskId=r.task_id;switchTab('live');refreshAll()}}
```

- [ ] Commit: `git add delegator/dashboard/templates/dashboard.html && git commit -m "fix: add exportLogs, clearLogs, exportHistory, execFromQueue functions"`

---

### Task 3: Fix 12 stub functions — make them real

**Files:** `delegator/dashboard/templates/dashboard.html` + `delegator/dashboard/api.py`

- [ ] Replace `viewDelegation(id)` to show real data:

```javascript
async function viewDelegation(id){const d=await api('/api/metrics?days=30&limit=50');if(!d)return;const del=d.delegations.find(r=>r.id===id);if(del){const deets=`Task: ${del.task_type||'?'} Workflow: ${del.workflow} Agent: ${del.to_agent} Model: ${del.model} Duration: ${del.duration_ms}ms Fallbacks: ${del.fallback_count} Success: ${del.success}`;alert(deets)}else{alert('Task not found')}}
```

- [ ] Replace `sendTestWebhook()` to actually call the API:

```javascript
async function sendTestWebhook(){const c=document.querySelectorAll('#set-notifications .glass')[1];const inp=c?c.querySelectorAll('input:not([type=checkbox])'):[];const url=inp[0]?.value||'';if(!url){alert('Enter a webhook URL');return};const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'test_webhook',url})});alert(r?'Test sent! Check Slack/Discord.':'Send failed')}
```

- [ ] Replace `resetRankings()` to call API:

```javascript
async function resetRankings(){const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'reset_rankings'})});alert(r?'Rankings reset':'Failed')}
```

- [ ] Add `reset_rankings` handler to post_config in api.py:
```python
if key == "reset_rankings":
    from delegator.state import rankings_path
    save_json(str(rankings_path()), {})
    return {"status": "ok", "message": "Rankings reset"}
```

- [ ] Fix Cmd+K to focus search input instead of alert
- [ ] Fix +Slack/Discord/Email buttons to actually add input fields instead of alert
- [ ] Fix +Add Route and Save Routes to have real handlers
- [ ] Fix Analytics PDF to generate a real printable page

- [ ] Commit: `git add delegator/dashboard/api.py delegator/dashboard/templates/dashboard.html && git commit -m "fix: convert 12 stub functions to real implementations"`

---

### Task 4: Add Compare model selectors + fix hardcoded row handlers

**Files:** `delegator/dashboard/templates/dashboard.html`

- [ ] Add model selector dropdowns to Compare tab:

Replace the static "A: opencode-go/deepseek-v4-pro" and "B: claude-sonnet-4-6" text with select dropdowns:
```html
<select class="select text-xs" id="compare-model-a"><option>opencode-go/deepseek-v4-pro</option><option>claude-sonnet-4-6</option><option>opencode-go/minimax-m2.7</option><option>federated-coding</option><option>federated-free</option></select>
```

- [ ] Update `runCompare()` to read from selectors instead of hardcoded values
- [ ] Add Stop Both button handler: `onclick="stopTask();stopTask()"`

- [ ] Commit: `git add delegator/dashboard/templates/dashboard.html && git commit -m "feat: compare model selectors + hardcoded row fixes"`

---

### Task 5: Fix hardcoded HTML handlers + Logs search

**Files:** `delegator/dashboard/templates/dashboard.html`

- [ ] Add search handler to Logs search input: `onkeyup="searchLogs(this.value)"`

```javascript
function searchLogs(q){const rows=document.querySelectorAll('#tab-logs .t-body > div');rows.forEach(r=>{const t=r.textContent.toLowerCase();r.style.display=t.includes(q.toLowerCase())?'':'none'})}
```

- [ ] Add onclick handlers to Route editor ✕ button (remove route row)
- [ ] Add onclick to Stop Both in Compare tab
- [ ] Add onclick to Edit buttons in Queue dynamic rows

- [ ] Commit: `git add delegator/dashboard/templates/dashboard.html && git commit -m "fix: search, route editor, compare stop, queue edit buttons"`

---

### Task 6: Verify + Re-audit

- [ ] Run all tests: `cd ~/delegator && python -m pytest tests/ -v`
- [ ] Restart server and verify all endpoints
- [ ] Check that all 36 gaps are now REAL
- [ ] Commit final
