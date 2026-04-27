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
    print(f"Delegator Dashboard \u2192 http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
