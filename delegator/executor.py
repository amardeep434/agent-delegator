"""Core execution - runs tasks with federated failover across providers."""

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from delegator.models import DelegationRequest, DelegationResult
from delegator.registry import load_registry
from delegator.router import resolve_route
from delegator.resolver import resolve_logical_model, resolve_model, build_cli_command
from delegator.cooldowns import is_cooled_down, record_failure, record_success
from delegator.handoff import write_handoff
from delegator.metrics import record_delegation
from delegator.optimizer import get_rankings


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


def _try_handoff(delegate_agent, logical_providers, i, task, model, worktree):
    next_idx = i + 1
    if next_idx < len(logical_providers):
        next_provider = logical_providers[next_idx].split(":", 1)
        if len(next_provider) == 2:
            try:
                write_handoff(
                    from_agent=delegate_agent,
                    to_agent=next_provider[0],
                    task=task,
                    prev_model=model,
                    worktree=worktree,
                )
            except Exception:
                pass


def _setup_signal_handler(worktree_path: str, project_root: str):
    def cleanup_handler(signum, frame):
        if os.path.exists(worktree_path):
            try:
                subprocess.run(
                    ["git", "-C", project_root, "worktree", "remove", "--force", worktree_path],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass
        os._exit(1)
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)


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

    rankings = get_rankings()
    if rankings:
        scored = []
        for pk in logical_providers:
            parts = pk.split(":", 1)
            if len(parts) == 2:
                agent_key = parts[0]
                score = rankings.get("rankings", {}).get(agent_key, {}).get("score", 0.0)
                scored.append((pk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        logical_providers = [s[0] for s in scored]

    project = project_root or os.getcwd()
    worktree = str(Path(project))

    if not request.no_worktree:
        worktree = str(_create_worktree(project, request.id))
        _setup_signal_handler(worktree, project)
    else:
        worktree = str(Path(project))

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

        timeout_event = threading.Event()
        proc = None

        def on_timeout():
            timeout_event.set()
            if proc:
                proc.kill()

        timer = threading.Timer(600, on_timeout)
        try:
            stream_mode = getattr(request, 'stream', False)
            with open(log_path, "w") as log_file:
                proc = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=worktree, preexec_fn=os.setsid, bufsize=1, text=True
                )
                timer.start()
                for line in proc.stdout:
                    log_file.write(line)
                    log_file.flush()
                    if stream_mode:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                proc.wait()
                timer.cancel()
        except subprocess.TimeoutExpired:
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = "timeout"
            _try_handoff(delegate_agent, logical_providers, i, request.task, model, worktree)
            continue
        except Exception as e:
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = str(e)[:200]
            _try_handoff(delegate_agent, logical_providers, i, request.task, model, worktree)
            continue
        finally:
            if timer.is_alive():
                timer.cancel()

        if _check_failure(log_path, registry):
            record_failure(agent, model, registry)
            fallback_count += 1
            last_error = "rate_limit_or_failure"
            _try_handoff(delegate_agent, logical_providers, i, request.task, model, worktree)
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
