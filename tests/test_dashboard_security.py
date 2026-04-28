"""Security tests for dashboard server."""
import inspect
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_delegator.dashboard import server as srv


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
    assert "Referrer-Policy" in src
    assert "Permissions-Policy" in src


def test_api_key_required_for_api_endpoints():
    # Verify that API key check is present in GET handlers
    src = inspect.getsource(srv.DashboardHandler.do_GET)
    assert "_check_api_key" in src
    assert "Unauthorized" in src

    # Verify that API key check is present in POST handlers
    src = inspect.getsource(srv.DashboardHandler.do_POST)
    assert "_check_api_key" in src


def test_api_key_is_loaded_or_created():
    with tempfile.TemporaryDirectory() as tmp:
        key_file = Path(tmp) / "dashboard.key"
        with patch.object(srv, "_API_KEY_FILE", key_file):
            key = srv._load_or_create_api_key()
            assert len(key) > 20
            assert key_file.exists()
            # Should load existing key on second call
            key2 = srv._load_or_create_api_key()
            assert key == key2


def test_rate_limit_uses_direct_ip():
    src = inspect.getsource(srv._get_client_ip)
    # Should not blindly trust X-Forwarded-For
    assert "X-Forwarded-For" not in src


def test_get_routes_does_not_leak_internal_state():
    from agent_delegator.dashboard.api import get_routes
    data = get_routes()
    for route in data["routes"]:
        assert "/" not in route["agent"]
        assert isinstance(route["workflow"], str)


def test_ssrf_blocked_for_internal_urls():
    from agent_delegator.dashboard.api import _is_internal_url
    assert _is_internal_url("http://localhost:8080/")
    assert _is_internal_url("http://127.0.0.1/test")
    assert _is_internal_url("http://169.254.169.254/metadata")
    assert _is_internal_url("http://metadata.google.internal/")
    assert _is_internal_url("http://10.0.0.1/test")
    assert _is_internal_url("http://192.168.1.1/test")
    assert not _is_internal_url("https://api.telegram.org/bot123/sendMessage")
    assert not _is_internal_url("https://hooks.slack.com/services/xxx")


def test_telegram_token_validation():
    from agent_delegator.dashboard.api import _TELEGRAM_TOKEN_RE
    assert _TELEGRAM_TOKEN_RE.match("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    assert not _TELEGRAM_TOKEN_RE.match("invalid-token")
    assert not _TELEGRAM_TOKEN_RE.match("")


def test_url_validation():
    from agent_delegator.dashboard.api import _URL_RE
    assert _URL_RE.match("https://hooks.slack.com/services/xxx")
    assert _URL_RE.match("http://example.com")
    assert not _URL_RE.match("ftp://example.com")
    assert not _URL_RE.match("javascript:alert(1)")
    assert not _URL_RE.match("not-a-url")


def test_task_validation_blocks_shell_meta():
    from agent_delegator.dashboard.api import _validate_task
    ok, _ = _validate_task("Implement a feature")
    assert ok
    ok, msg = _validate_task("")
    assert not ok
    ok, msg = _validate_task("x" * 6000)
    assert not ok
    ok, msg = _validate_task("task; rm -rf /")
    assert not ok
    ok, msg = _validate_task("task $(whoami)")
    assert not ok
    ok, msg = _validate_task("task `whoami`")
    assert not ok


def test_post_project_rejects_invalid_paths():
    from agent_delegator.dashboard.api import post_project
    assert post_project({"path": "/nonexistent"})["status"] == "error"
    assert post_project({"path": "../../etc"})["status"] == "error"
    assert post_project({"path": 123})["status"] == "error"


def test_post_config_rejects_invalid_test_telegram():
    from agent_delegator.dashboard.api import post_config
    result = post_config({"key": "test_telegram", "token": "bad", "chat_id": "123"})
    assert result["status"] == "error"


def test_post_config_rejects_invalid_test_webhook():
    from agent_delegator.dashboard.api import post_config
    result = post_config({"key": "test_webhook", "url": "javascript:alert(1)"})
    assert result["status"] == "error"
    result = post_config({"key": "test_webhook", "url": "http://127.0.0.1/hook"})
    assert result["status"] == "error"


def test_post_config_validates_cooldown_config_type():
    from agent_delegator.dashboard.api import post_config
    result = post_config({"key": "cooldown", "config": "not-a-dict"})
    assert result["status"] == "error"


def test_post_config_enforces_queue_limits():
    from agent_delegator.dashboard.api import post_config, _MAX_QUEUE_SIZE, _MAX_SCHEDULED_SIZE
    # Reset queues for test
    import agent_delegator.dashboard.api as api_mod
    original_queue = api_mod._pending_queue[:]
    original_scheduled = api_mod._scheduled_tasks[:]
    api_mod._pending_queue.clear()
    api_mod._scheduled_tasks.clear()
    try:
        # Fill queue to limit
        for i in range(_MAX_QUEUE_SIZE + 2):
            result = post_config({"key": "add_pending", "task": f"task {i}"})
        # One should have failed
        assert result["status"] == "error"
        # Fill scheduled to limit
        for i in range(_MAX_SCHEDULED_SIZE + 2):
            result = post_config({"key": "add_scheduled", "task": f"task {i}", "cron": "0 0 * * *"})
        assert result["status"] == "error"
    finally:
        api_mod._pending_queue[:] = original_queue
        api_mod._scheduled_tasks[:] = original_scheduled
