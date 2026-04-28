# Agent Instructions for Delegator

## Project Overview

Agent-agnostic AI CLI delegation with federated model failover. This project includes a local HTTP dashboard (`agent-delegator/dashboard/`) for monitoring and controlling agent execution.

## Build & Test

```bash
# Run all tests
python -m pytest tests/ -v

# Run dashboard tests only
python -m pytest tests/test_dashboard.py tests/test_dashboard_security.py -v

# Start dashboard server
python -m agent_delegator.dashboard.server
```

## Security Requirements (MANDATORY)

All changes to the dashboard or any feature processing user input MUST pass the security checklist. These are non-negotiable.

### Critical Rules

1. **Never trust user input.** Validate type, length, and content before processing.
2. **Never return raw exceptions to clients.** Use generic messages; log details server-side.
3. **Never trust `X-Forwarded-For` or `Origin` headers alone.** Use direct IP for rate limiting.
4. **Never construct URLs with unvalidated user input.** SSRF checks are mandatory.
5. **Never insert user data into DOM without escaping.** XSS prevention is mandatory.

### Checklist for Every Dashboard Change

- [ ] API key auth (`X-API-Key`) enforced on all endpoints
- [ ] Rate limiting applied with direct IP (no forwarded headers)
- [ ] CSRF protection (`X-Requested-With` + Origin/Referer)
- [ ] Input validation (type, length, shell meta chars)
- [ ] XSS escaping (`escapeHtml()` / `escapeAttr()`) on all dynamic DOM insertion
- [ ] No inline `onclick` with user data (use `data-*` + `addEventListener`)
- [ ] SSRF checks on all outbound URLs (`_is_internal_url()`)
- [ ] Security headers present on all responses
- [ ] Generic error messages to clients
- [ ] Security tests added/updated in `tests/test_dashboard_security.py`
- [ ] All tests pass

### File Locations

- `agent-delegator/dashboard/server.py` — HTTP server, auth, rate limiting, headers
- `agent-delegator/dashboard/api.py` — API endpoints, validation, outbound requests
- `agent-delegator/dashboard/templates/dashboard.html` — Frontend, XSS prevention
- `agent-delegator/secrets.py` — Encryption for sensitive config
- `tests/test_dashboard_security.py` — Security regression tests
- `.claude/skills/security-dashboard-hardening/SKILL.md` — Full security skill
- `.claude/hookify.*.local.md` — Automated security rule hooks

## Coding Conventions

- Python: PEP 8, type hints where helpful
- JavaScript: ES6+, no `var`, prefer `const`
- HTML: Escape all dynamic values before insertion
- Security first: If unsure, block and ask
