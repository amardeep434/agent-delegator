"""Core execution - runs tasks with federated failover across providers."""

import os
import re
import subprocess
import time
from pathlib import Path
from delegator.models import DelegationRequest, DelegationResult
from delegator.registry import load_registry
from delegator.router import resolve_route
from delegator.resolver import resolve_logical_model, resolve_model, build_cli_command
from delegator.cooldowns import is_cooled_down, record_failure, record_success
from delegator.handoff import write_handoff
from delegator.metrics import record_delegation


def _check_rate_limit(output: str, registry: dict) -> bool:
    """Check if output contains rate limit patterns."""
    patterns = registry.get("rate_limit_patterns", [])
    lower = output.lower()
    for pattern in patterns:
        if re.search(pattern, lower):
            return True
    return False


def _check_failure(log_path: str, registry: dict) -> bool:
    """Check if a log file indicates failure."""
    if not os.path.exists(log_path):
        return True
    try:
        with open(log_path, "r") as f:
            return _check_rate_limit(f.read(), registry)
    except Exception:
        return True


def _create_worktree(project_root: str, task_id: str) -> Path:
    """Create a git worktree for isolated delegation."""
    delegation_dir = Path(project_root) / ".delegation" / "worktrees"
    delegation_dir.mkdir(parents=True, exist_ok=True)
    worktree_path = delegation_dir / task_id

    try:
        subprocess.run(
            ["git", "-C", project_root, "worktree", "add", str(worktree_path)],
            capture_output=True, text=True, timeout=30
        )
    except Exception:
        worktree_path.mkdir(parents=True, exist_ok=True)

    return worktree_path


def execute(request: DelegationRequest, project_root: str | None = None) -> DelegationResult:
    """Execute a delegation request with federated failover.

    Flow:
    1. Resolve route (agent + model)
    2. If logical model, try each provider in order
    3. On rate limit failure, try next provider
    4. Track cooldowns
    """
    registry = load_registry(project_root)
    start_time = time.time()

    delegate_agent, preferred_model = resolve_route(
        registry, request.workflow, request.task_type or "implementation", request.from_agent
    )

    model_name = request.model or preferred_model
    logical_providers = resolve_logical_model(registry, model_name)

    if not logical_providers:
        logical_providers = [f"{delegate_agent}:{model_name}"]

    project = project_root or os.getcwd()
    worktree = str(Path(project))

    if not request.no_worktree:
        worktree = str(_create_worktree(project, request.id))

    last_error = None
    fallback_count = 0

    for i, provider_key in enumerate(logical_providers):
        parts = provider_key.split(":", 1)
        if len(parts) != 2:
            continue
        agent, model = parts

        if is_cooled_down(agent, model):
            fallback_count += 1
            continue

        try:
            resolved_model = resolve_model(registry, model, agent)
            cmd = build_cli_command(registry, agent, resolved_model, request.task, worktree)
        except ValueError:
            continue

        log_path = os.path.join(worktree, f"agent_{i}.log")

        try:
            subprocess.run(
                f"{cmd} 2>&1 > {log_path}", shell=True,
                timeout=600, cwd=worktree
            )
        except subprocess.TimeoutExpired:
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = "timeout"
            next_idx = i + 1
            if next_idx < len(logical_providers):
                next_provider = logical_providers[next_idx].split(":", 1)
                if len(next_provider) == 2:
                    write_handoff(
                        from_agent=delegate_agent,
                        to_agent=next_provider[0],
                        task=request.task,
                        prev_model=model,
                        worktree=worktree,
                    )
            continue
        except Exception as e:
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = str(e)[:200]
            next_idx = i + 1
            if next_idx < len(logical_providers):
                next_provider = logical_providers[next_idx].split(":", 1)
                if len(next_provider) == 2:
                    write_handoff(
                        from_agent=delegate_agent,
                        to_agent=next_provider[0],
                        task=request.task,
                        prev_model=model,
                        worktree=worktree,
                    )
            continue

        if _check_failure(log_path, registry):
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = "rate_limit_or_failure"
            next_idx = i + 1
            if next_idx < len(logical_providers):
                next_provider = logical_providers[next_idx].split(":", 1)
                if len(next_provider) == 2:
                    write_handoff(
                        from_agent=delegate_agent,
                        to_agent=next_provider[0],
                        task=request.task,
                        prev_model=model,
                        worktree=worktree,
                    )
            continue

        record_success(agent, model)
        duration_ms = int((time.time() - start_time) * 1000)

        output_text = ""
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    output_text = f.read()
            except Exception:
                pass

        record_delegation(
            request_id=request.id,
            from_agent=request.from_agent or "",
            to_agent=agent,
            model=model_name,
            provider_used=agent,
            workflow=request.workflow,
            task_type=request.task_type or "implementation",
            success=True,
            fallback_count=fallback_count,
            duration_ms=duration_ms,
        )

        return DelegationResult(
            success=True,
            provider_used=agent,
            model_used=model,
            fallback_count=fallback_count,
            output=output_text,
            duration_ms=duration_ms,
            request_id=request.id,
        )

    duration_ms = int((time.time() - start_time) * 1000)
    record_delegation(
        request_id=request.id,
        from_agent=request.from_agent or "",
        to_agent=delegate_agent,
        model=model_name,
        provider_used="",
        workflow=request.workflow,
        task_type=request.task_type or "implementation",
        success=False,
        fallback_count=fallback_count,
        duration_ms=duration_ms,
    )
    return DelegationResult(
        success=False,
        provider_used="",
        model_used="",
        fallback_count=fallback_count,
        error=last_error or "all_providers_failed",
        duration_ms=duration_ms,
        request_id=request.id,
    )
