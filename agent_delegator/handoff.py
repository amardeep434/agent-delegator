"""Context handoff - generates HANDOFF.md when switching agents."""

import os
import subprocess
from pathlib import Path


TEMPLATE = """# Handoff Summary

**From:** {from_agent}
**To:** {to_agent}
**Task:** {task}
**Previous Model:** {prev_model}

## Progress
{progress}

## Files Modified
{files}

## Next Steps
{next_steps}
"""


def generate_handoff(
    from_agent: str,
    to_agent: str,
    task: str,
    prev_model: str,
    progress: str = "",
    worktree: str = "",
    next_steps: str = "Continue the task where the previous agent left off."
) -> str:
    """Generate a handoff markdown file for context transfer between agents."""
    files = ""
    if worktree and os.path.exists(worktree):
        try:
            result = subprocess.run(
                ["git", "-C", worktree, "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                files = "\n".join(f"- {f}" for f in result.stdout.strip().split("\n"))
        except Exception:
            pass

    content = TEMPLATE.format(
        from_agent=from_agent,
        to_agent=to_agent,
        task=task,
        prev_model=prev_model,
        progress=progress,
        files=files or "- No tracked file changes",
        next_steps=next_steps,
    )
    return content


def write_handoff(
    from_agent: str,
    to_agent: str,
    task: str,
    prev_model: str,
    worktree: str = "",
    progress: str = "",
) -> Path:
    """Generate and write HANDOFF.md to the worktree."""
    content = generate_handoff(from_agent, to_agent, task, prev_model, progress, worktree)
    target = Path(worktree) if worktree else Path.cwd()
    handoff_path = target / "HANDOFF.md"
    handoff_path.write_text(content)
    return handoff_path
