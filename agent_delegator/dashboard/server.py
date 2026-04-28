"""HTTP server for delegator dashboard. Binds to 127.0.0.1 only."""

import http.server
import json
import os
import secrets
import time
import urllib.parse
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
MAX_BODY_SIZE = 1024 * 16  # 16KB max request body

# Simple in-memory rate limiter: client_ip -> {count, reset_time}
_rate_limit_store = {}
_rate_limit_window = 60  # seconds
_rate_limit_max = 60     # requests per window

# API key storage
_STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))) / "agent-delegator"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_API_KEY_FILE = _STATE_DIR / "dashboard.key"


def _load_or_create_api_key() -> str:
    if _API_KEY_FILE.exists():
        return _API_KEY_FILE.read_text().strip()
    key = secrets.token_urlsafe(32)
    _API_KEY_FILE.write_text(key)
    # Restrict permissions (owner read/write only)
    os.chmod(_API_KEY_FILE, 0o600)
    return key


_API_KEY = _load_or_create_api_key()


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    entry = _rate_limit_store.get(client_ip, {"count": 0, "reset": now + _rate_limit_window})
    if now > entry["reset"]:
        entry = {"count": 0, "reset": now + _rate_limit_window}
    entry["count"] += 1
    _rate_limit_store[client_ip] = entry
    # Clean old entries periodically
    if len(_rate_limit_store) > 1000:
        cutoff = now - _rate_limit_window
        for ip in list(_rate_limit_store.keys()):
            if _rate_limit_store[ip]["reset"] < cutoff:
                del _rate_limit_store[ip]
    return entry["count"] <= _rate_limit_max


def _json_response(handler, data, status=200):
    """Send a JSON response with security headers."""
    body = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
    handler.send_header("Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()")
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


def _get_client_ip(handler) -> str:
    # Use direct connection IP. Never trust forwarded headers for
    # localhost-only services without explicit trusted proxy config.
    return handler.client_address[0]


def _validate_origin(handler) -> bool:
    """CSRF protection: validate Origin/Referer for POST requests."""
    origin = handler.headers.get("Origin", "")
    referer = handler.headers.get("Referer", "")
    host = handler.headers.get("Host", "127.0.0.1:8765")
    # For local development, accept requests from the same host
    allowed_prefixes = (f"http://{host}", f"https://{host}")
    if origin and not origin.startswith(allowed_prefixes):
        return False
    if referer and not referer.startswith(allowed_prefixes):
        return False
    return True


def _check_api_key(handler) -> bool:
    """Require X-API-Key header for API endpoints."""
    key = handler.headers.get("X-API-Key", "").strip()
    return key == _API_KEY


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """Request handler with route dispatch and security checks."""

    def do_GET(self):
        client_ip = _get_client_ip(self)
        if not _check_rate_limit(client_ip):
            _json_response(self, {"status": "error", "message": "Rate limit exceeded"}, 429)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._serve_html("dashboard.html")
        elif path == "/api/projects":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            from agent_delegator.dashboard.api import get_projects
            _json_response(self, get_projects())
        elif path.startswith("/api/agents/"):
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            agent_name = path.split("/")[3] if len(path.split("/")) > 3 else ""
            from agent_delegator.dashboard.api import get_agent_models
            _json_response(self, get_agent_models(agent_name))
        elif path == "/api/status":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            from agent_delegator.dashboard.api import get_status
            _json_response(self, get_status())
        elif path == "/api/metrics":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            agent = (params.get("agent", [None])[0] or "").strip()
            days = (params.get("days", ["7"])[0]).strip()
            from agent_delegator.dashboard.api import get_metrics
            _json_response(self, get_metrics(agent=agent or None, days=int(days)))
        elif path == "/api/logs":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            agent = (params.get("agent", [None])[0] or "").strip()
            level = (params.get("level", [None])[0] or "").strip()
            limit = (params.get("limit", ["200"])[0]).strip()
            from agent_delegator.dashboard.api import get_logs
            _json_response(self, get_logs(agent=agent or None, level=level or None, limit=int(limit)))
        elif path == "/api/routes":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            from agent_delegator.dashboard.api import get_routes
            _json_response(self, get_routes())
        elif path == "/api/config":
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            from agent_delegator.dashboard.api import get_config
            _json_response(self, get_config())
        elif path.startswith("/api/tasks/") and path.endswith("/output"):
            if not _check_api_key(self):
                _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
                return
            task_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
            from agent_delegator.dashboard.api import get_task_output
            _json_response(self, get_task_output(task_id))
        else:
            self.send_error(404)

    def do_POST(self):
        client_ip = _get_client_ip(self)
        if not _check_rate_limit(client_ip):
            _json_response(self, {"status": "error", "message": "Rate limit exceeded"}, 429)
            return

        # CSRF protection
        if not _validate_origin(self):
            _json_response(self, {"status": "error", "message": "Invalid origin"}, 403)
            return

        # Require X-Requested-With header for API calls (additional CSRF protection)
        if not self.headers.get("X-Requested-With", "").strip():
            _json_response(self, {"status": "error", "message": "Missing X-Requested-With header"}, 403)
            return

        # API key auth
        if not _check_api_key(self):
            _json_response(self, {"status": "error", "message": "Unauthorized"}, 401)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = _read_body(self)
        except (ValueError, json.JSONDecodeError) as e:
            _json_response(self, {"status": "error", "message": "Invalid request body"}, 400)
            return

        if path == "/api/exec":
            from agent_delegator.dashboard.api import post_exec
            _json_response(self, post_exec(body))
        elif path == "/api/config":
            from agent_delegator.dashboard.api import post_config
            _json_response(self, post_config(body))
        elif path == "/api/compare":
            from agent_delegator.dashboard.api import post_compare
            _json_response(self, post_compare(body))
        elif path == "/api/projects":
            from agent_delegator.dashboard.api import post_project
            _json_response(self, post_project(body))
        elif path.startswith("/api/tasks/") and path.endswith("/stop"):
            task_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
            from agent_delegator.dashboard.api import post_stop_task
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
        content = filepath.read_text(encoding="utf-8")
        # Inject API key into page so the SPA can use it
        content = content.replace(
            "</head>",
            f'<meta name="api-key" content="{_API_KEY}"></head>'
        )
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        """Log requests for audit trail."""
        client_ip = self.client_address[0]
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {client_ip} - {format % args}")


def run_server(port=8765):
    """Start dashboard server on 127.0.0.1:port."""
    server = http.server.HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"Delegator Dashboard \u2192 http://127.0.0.1:{port}")
    print(f"API Key: {_API_KEY}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
