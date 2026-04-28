#!/usr/bin/env python3
"""Bump version based on conventional commits since last tag."""

import os
import re
import subprocess
import sys


def run(cmd: str) -> str:
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()


def get_latest_tag() -> str | None:
    try:
        return run("git describe --tags --abbrev=0")
    except subprocess.CalledProcessError:
        return None


def get_commits_since(tag: str | None) -> list[str]:
    if tag is None:
        return run("git log --pretty=format:%s").split("\n")
    return run(f'git log {tag}..HEAD --pretty=format:%s').split("\n")


def determine_bump(commits: list[str]) -> str | None:
    """Return 'major', 'minor', 'patch', or None."""
    has_breaking = False
    has_feat = False
    has_fix = False

    for msg in commits:
        if not msg:
            continue
        lower = msg.lower()
        if "breaking change" in lower or "breaking:" in lower:
            has_breaking = True
        if msg.startswith("feat(") or msg.startswith("feat:"):
            has_feat = True
        if msg.startswith("fix(") or msg.startswith("fix:"):
            has_fix = True

    if has_breaking:
        return "major"
    if has_feat:
        return "minor"
    if has_fix:
        return "patch"
    return None


def parse_version(version: str) -> tuple[int, int, int]:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        raise ValueError(f"Invalid version: {version}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_version(current: str, bump: str) -> str:
    major, minor, patch = parse_version(current)
    if bump == "major":
        return f"{major + 1}.0.0"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def update_version_file(new_version: str) -> None:
    # Update __init__.py
    init_path = "agent_delegator/__init__.py"
    with open(init_path) as f:
        content = f.read()
    content = re.sub(
        r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', content
    )
    with open(init_path, "w") as f:
        f.write(content)

    # Update pyproject.toml
    toml_path = "pyproject.toml"
    with open(toml_path) as f:
        content = f.read()
    content = re.sub(
        r'version\s*=\s*"[^"]+"', f'version = "{new_version}"', content
    )
    with open(toml_path, "w") as f:
        f.write(content)


def main() -> int:
    latest_tag = get_latest_tag()
    commits = get_commits_since(latest_tag)
    bump = determine_bump(commits)

    if bump is None:
        print("No version-bumping commits found. Skipping release.")
        # Write empty version so workflow knows to skip
        with open(".version", "w") as f:
            f.write("")
        return 0

    current_version = latest_tag.lstrip("v") if latest_tag else "0.0.0"
    new_version = bump_version(current_version, bump)

    print(f"Bumping {current_version} → {new_version} ({bump})")

    update_version_file(new_version)

    # Commit version bump
    run("git add agent_delegator/__init__.py pyproject.toml")
    run(f'git commit -m "bump: version {new_version}"')
    run(f'git tag v{new_version}')
    run("git push origin HEAD --tags")

    with open(".version", "w") as f:
        f.write(new_version)

    return 0


if __name__ == "__main__":
    sys.exit(main())
