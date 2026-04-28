"""Worktree cleanup - removes stale worktrees past TTL."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from agent_delegator.state import worktrees_dir


def cleanup_stale_worktrees(project_root: str, ttl_hours: int = 24) -> int:
    """Remove worktrees older than ttl_hours. Returns count removed."""
    wdir = worktrees_dir(project_root)
    if not wdir.exists():
        return 0

    cutoff = time.time() - (ttl_hours * 3600)
    removed = 0

    for entry in wdir.iterdir():
        try:
            if entry.is_symlink():
                continue
            if not entry.is_dir():
                continue
            mtime = entry.stat().st_mtime
            if mtime < cutoff:
                shutil.rmtree(entry)
                subprocess.run(
                    ["git", "-C", project_root, "worktree", "prune"],
                    capture_output=True
                )
                removed += 1
        except Exception:
            pass

    return removed
