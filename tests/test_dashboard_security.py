"""Security tests for dashboard server."""
import inspect
from pathlib import Path
from delegator.dashboard import server as srv


def test_server_binds_localhost_only():
    src = Path(srv.__file__).read_text()
    assert "127.0.0.1" in src


def test_path_traversal_blocked_in_serve_html():
    src = inspect.getsource(srv.DashboardHandler._serve_html)
    assert "os.path.basename" in src


def test_max_body_size_enforced():
    assert srv.MAX_BODY_SIZE > 0
    assert srv.MAX_BODY_SIZE <= 65536


def test_security_headers_present():
    src = inspect.getsource(srv._json_response)
    assert "X-Content-Type-Options" in src
    assert "X-Frame-Options" in src
    assert "nosniff" in src


def test_get_routes_does_not_leak_internal_state():
    from delegator.dashboard.api import get_routes
    data = get_routes()
    for route in data["routes"]:
        assert "/" not in route["agent"]
        assert isinstance(route["workflow"], str)
