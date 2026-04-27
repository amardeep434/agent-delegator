"""State directory management for delegator."""

import os
from pathlib import Path


def state_dir() -> Path:
    """Return the delegator state directory, creating it if needed."""
    xdg = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    path = Path(xdg) / "delegator"
    path.mkdir(parents=True, exist_ok=True)
    return path


def metrics_db_path() -> Path:
    """Path to the SQLite metrics database."""
    return state_dir() / "metrics.db"


def cooldowns_path() -> Path:
    """Path to the cooldowns JSON file."""
    return state_dir() / "cooldowns.json"


def capabilities_path() -> Path:
    """Path to the capabilities JSON file."""
    return state_dir() / "capabilities.json"


def rankings_path() -> Path:
    """Path to the learned provider rankings JSON file."""
    return state_dir() / "provider_rankings.json"


def worktrees_dir(project_root: str | None = None) -> Path:
    """Path to project-local worktrees directory."""
    if project_root:
        path = Path(project_root) / ".delegation" / "worktrees"
    else:
        path = Path.cwd() / ".delegation" / "worktrees"
    path.mkdir(parents=True, exist_ok=True)
    return path


def likes_path() -> Path:
    """Path to the delegation likes JSON file."""
    return state_dir() / "likes.json"
