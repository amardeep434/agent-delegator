"""SQLite metrics storage for delegation analytics."""

import sqlite3
from delegator.state import metrics_db_path


def _get_db() -> sqlite3.Connection:
    """Get a connection to the metrics database, creating tables if needed."""
    path = str(metrics_db_path())
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delegations (
            id TEXT PRIMARY KEY,
            from_agent TEXT,
            to_agent TEXT,
            model TEXT,
            provider_used TEXT,
            workflow TEXT,
            task_type TEXT,
            success INTEGER,
            fallback_count INTEGER,
            duration_ms INTEGER,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def record_delegation(
    request_id: str,
    from_agent: str,
    to_agent: str,
    model: str,
    provider_used: str,
    workflow: str,
    task_type: str,
    success: bool,
    fallback_count: int,
    duration_ms: int,
) -> None:
    """Record a delegation result."""
    conn = _get_db()
    conn.execute(
        """INSERT OR REPLACE INTO delegations
           (id, from_agent, to_agent, model, provider_used, workflow, task_type, success, fallback_count, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (request_id, from_agent, to_agent, model, provider_used, workflow, task_type, int(success), fallback_count, duration_ms),
    )
    conn.commit()
    conn.close()


def get_success_rate(agent: str | None = None, days: int = 7) -> float:
    """Get success rate for an agent or overall."""
    conn = _get_db()
    if agent:
        row = conn.execute(
            "SELECT COUNT(*), SUM(success) FROM delegations WHERE to_agent = ? AND timestamp >= datetime('now', ?)",
            (agent, f"-{days} days"),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*), SUM(success) FROM delegations WHERE timestamp >= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchone()
    conn.close()
    total, successes = row
    if not total:
        return 1.0
    return successes / total


def get_recent_delegations(limit: int = 20) -> list[dict]:
    """Get recent delegation records."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM delegations ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    cols = ["id", "from_agent", "to_agent", "model", "provider_used", "workflow", "task_type", "success", "fallback_count", "duration_ms", "timestamp"]
    return [dict(zip(cols, row)) for row in rows]
