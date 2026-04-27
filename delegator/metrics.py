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
            cost REAL DEFAULT 0,
            failure_type TEXT DEFAULT '',
            liked INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    _migrate_db(conn)
    return conn


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add any missing columns to the delegations table."""
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(delegations)")
    }
    if "cost" not in existing:
        conn.execute("ALTER TABLE delegations ADD COLUMN cost REAL DEFAULT 0")
    if "failure_type" not in existing:
        conn.execute("ALTER TABLE delegations ADD COLUMN failure_type TEXT DEFAULT ''")
    if "liked" not in existing:
        conn.execute("ALTER TABLE delegations ADD COLUMN liked INTEGER DEFAULT 0")
    conn.commit()


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
    cost: float = 0,
    failure_type: str = "",
) -> None:
    """Record a delegation result."""
    conn = _get_db()
    conn.execute(
        """INSERT OR REPLACE INTO delegations
           (id, from_agent, to_agent, model, provider_used, workflow, task_type, success, fallback_count, duration_ms, cost, failure_type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (request_id, from_agent, to_agent, model, provider_used, workflow, task_type, int(success), fallback_count, duration_ms, cost, failure_type),
    )
    conn.commit()
    conn.close()


def set_liked(delegation_id: str, liked: bool) -> None:
    """Update the liked status for a delegation."""
    conn = _get_db()
    conn.execute(
        "UPDATE delegations SET liked = ? WHERE id = ?",
        (int(liked), delegation_id),
    )
    conn.commit()
    conn.close()


def get_liked(delegation_id: str) -> bool:
    """Get the liked status for a delegation."""
    conn = _get_db()
    row = conn.execute(
        "SELECT liked FROM delegations WHERE id = ?",
        (delegation_id,),
    ).fetchone()
    conn.close()
    return bool(row[0]) if row else False


def classify_failure(success: bool, fallback_count: int, error: str | None) -> str:
    """Classify a failure based on success, fallback count, and error message."""
    if success:
        return ""
    if error is None:
        error = ""
    error_lower = error.lower()
    if "quota" in error_lower or "exceeded" in error_lower:
        return "quota_exceeded"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "model" in error_lower and ("not found" in error_lower or "not available" in error_lower or "unknown" in error_lower):
        return "model_not_found"
    if fallback_count > 0:
        return "rate_limit"
    return "exception"


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
    cols = ["id", "from_agent", "to_agent", "model", "provider_used", "workflow", "task_type", "success", "fallback_count", "duration_ms", "timestamp", "cost", "failure_type", "liked"]
    return [dict(zip(cols, row)) for row in rows]


def clear_delegations(prefix: str = "") -> None:
    """Delete delegations for testing. If prefix given, deletes only matching ids."""
    conn = _get_db()
    if prefix:
        conn.execute("DELETE FROM delegations WHERE id LIKE ?", (f"{prefix}%",))
    else:
        conn.execute("DELETE FROM delegations")
    conn.commit()
    conn.close()
