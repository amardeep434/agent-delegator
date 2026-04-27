"""CLI entry point for delegator - all commands via argparse."""

import argparse
import json
import os
import sys
from pathlib import Path
from delegator.models import DelegationRequest
from delegator.executor import execute
from delegator.registry import load_registry
from delegator.router import resolve_route
from delegator.resolver import resolve_logical_model
from delegator.cooldowns import get_active_cooldowns
from delegator.cleanup import cleanup_stale_worktrees
from delegator.health import check_all_agents
from delegator.capabilities import get_capabilities, discover_capabilities
from delegator.optimizer import optimize_rankings
from delegator.metrics import get_recent_delegations, get_success_rate


def cmd_exec(args):
    task = args.task_override or args.task or ""
    if args.from_file:
        task = Path(args.from_file).read_text().strip()
    if args.output:
        args.stream = False

    # Preview route before execution
    registry = load_registry()
    agent, model = resolve_route(
        registry, args.workflow, "implementation", args.from_agent or ""
    )
    resolved_model = args.model or model
    print(f"  route: {args.workflow} → {agent}")
    print(f"  model: {resolved_model}")
    if resolve_logical_model(registry, resolved_model):
        print(f"  providers: {', '.join(resolve_logical_model(registry, resolved_model))}")
    print()

    request = DelegationRequest(
        task=task,
        model=args.model,
        workflow=args.workflow,
        from_agent=args.from_agent,
        stream=args.stream,
        no_worktree=args.no_worktree,
    )
    result = execute(request)
    output = {
        "success": result.success,
        "provider_used": result.provider_used,
        "model_used": result.model_used,
        "fallback_count": result.fallback_count,
        "duration_ms": result.duration_ms,
    }
    if result.error:
        output["error"] = result.error
    if result.output and not args.stream:
        output["output"] = result.output

    output_json = json.dumps(output, indent=2)
    if args.output:
        Path(args.output).write_text(output_json)
        print(f"Output written to {args.output}")
    else:
        print(output_json)
    sys.exit(0 if result.success else 1)


def cmd_status(args):
    cooldowns = get_active_cooldowns()
    registry = load_registry()
    print("=== delegator status ===")
    print(f"Agents: {list(registry.get('agents', {}).keys())}")
    print(f"Active cooldowns: {len(cooldowns)}")
    if cooldowns:
        for key, entry in cooldowns.items():
            print(f"  {key}: cooldown until {entry['cooldown_until']}")
    recent = get_recent_delegations(5)
    print(f"Recent delegations: {len(recent)}")
    for d in recent:
        status = "OK" if d.get("success") else "FAIL"
        print(f"  [{status}] {d.get('to_agent')}:{d.get('model')} - {d.get('task_type', '')}")
    rate = get_success_rate(days=7)
    print(f"7-day success rate: {rate:.1%}")


def cmd_health(args):
    results = check_all_agents()
    for agent, status in results.items():
        icon = "OK" if status["available"] else "NG"
        print(f"[{icon}] {agent}: available={status['available']}, cli_found={status['cli_found']}")


def cmd_routes(args):
    registry = load_registry()
    matrix = registry.get("routing_matrix", {}).get("_any_agent_", {})
    for workflow, tasks in matrix.items():
        for task, route in tasks.items():
            print(f"{workflow}/{task} -> {route['delegate_to']}:{route['preferred_model']}")


def cmd_model(args):
    registry = load_registry()
    model_name = args.model
    providers = resolve_logical_model(registry, model_name)
    if providers:
        print(f"Logical model: {model_name}")
        for p in providers:
            print(f"  -> {p}")
    else:
        print(f"Model '{model_name}' - not a logical model, passed through directly.")


def cmd_cleanup(args):
    project = args.project or os.getcwd()
    removed = cleanup_stale_worktrees(project, ttl_hours=args.ttl)
    print(f"Removed {removed} stale worktrees (TTL: {args.ttl}h)")


def cmd_capabilities(args):
    caps = get_capabilities(args.agent) if args.agent else discover_capabilities()
    print(json.dumps(caps, indent=2))


def cmd_optimize(args):
    result = optimize_rankings()
    print("Optimized rankings:")
    for agent, data in result.get("rankings", {}).items():
        print(f"  {agent}: score={data['score']} (n={data['total_delegations']})")
    print(f"Recommended priority: {result.get('recommended_priority', [])}")


def cmd_learn(args):
    result = optimize_rankings()
    print(f"Learned from recent delegations. Rankings updated at {result['last_optimized']}")


def cmd_metrics(args):
    recent = get_recent_delegations(limit=args.limit)
    rate = get_success_rate(agent=args.agent, days=args.days)
    label = f"Success rate ({args.days}d"
    if args.agent:
        label += f", {args.agent}"
    label += f"): {rate:.1%}"
    print(label)
    print(f"Recent delegations ({len(recent)}):")
    for d in recent:
        status = "OK" if d.get("success") else "FAIL"
        print(f"  [{status}] {d.get('to_agent','?')}:{d.get('model','?')} - {d.get('workflow','?')}/{d.get('task_type','?')}")


def cmd_init(args):
    config_path = Path(args.project or os.getcwd()) / ".delegator.json"
    if config_path.exists():
        print(f"Config already exists at {config_path}")
        return
    template = {
        "preferred_models": {
            "implementation": "federated-coding",
            "code_review": "claude:claude-sonnet-4-6"
        },
        "provider_priority": ["claude", "opencode", "copilot"],
        "worktree_ttl_hours": 24,
        "cooldown_minutes": 5
    }
    config_path.write_text(json.dumps(template, indent=2) + "\n")
    print(f"Created {config_path}")


def cmd_config(args):
    config_path = Path(args.project or os.getcwd()) / ".delegator.json"
    if args.key:
        with open(config_path) as f:
            cfg = json.load(f)
        if args.value:
            cfg[args.key] = args.value
            config_path.write_text(json.dumps(cfg, indent=2) + "\n")
            print(f"Set {args.key} = {args.value}")
        else:
            print(f"{args.key}: {cfg.get(args.key)}")
    else:
        if config_path.exists():
            print(config_path.read_text())
        else:
            print("No .delegator.json in this project. Run 'delegator init'.")


def cmd_test(args):
    import subprocess as sp
    test_dir = Path(__file__).resolve().parent.parent / "tests"
    cmd = ["python", "-m", "pytest", str(test_dir), "-v"]
    if args.suite:
        cmd = ["python", "-m", "pytest", str(test_dir / f"test_{args.suite}.py"), "-v"]
    sp.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="delegator - Agent-agnostic AI CLI delegation")
    sub = parser.add_subparsers(dest="command")

    p_exec = sub.add_parser("exec", help="Execute delegation")
    p_exec.add_argument("task", nargs="?", default=None, help="Task description (positional)")
    p_exec.add_argument("-t", "--task", dest="task_override", default=None, help="Task description (alternative)")
    p_exec.add_argument("-m", "--model", required=True, help="Model to use")
    p_exec.add_argument("-w", "--workflow", default="subagent-driven", help="Workflow type")
    p_exec.add_argument("-f", "--from-agent", default="", help="Source agent")
    p_exec.add_argument("-s", "--stream", action="store_true", help="Stream output live")
    p_exec.add_argument("--no-worktree", action="store_true", help="Skip worktree creation")
    p_exec.add_argument("--from-file", default=None, help="Read task from file")
    p_exec.add_argument("-o", "--output", default=None, help="Write output to file")
    p_exec.set_defaults(func=cmd_exec)

    p_status = sub.add_parser("status", help="Show system status")
    p_status.set_defaults(func=cmd_status)

    p_health = sub.add_parser("health", help="Check agent availability")
    p_health.set_defaults(func=cmd_health)

    p_routes = sub.add_parser("routes", help="List available routes")
    p_routes.set_defaults(func=cmd_routes)

    p_model = sub.add_parser("model", help="Show model details")
    p_model.add_argument("model", metavar="model")
    p_model.set_defaults(func=cmd_model)

    p_cleanup = sub.add_parser("cleanup", help="Clean up stale worktrees")
    p_cleanup.add_argument("--project", default=None)
    p_cleanup.add_argument("--ttl", type=int, default=24)
    p_cleanup.set_defaults(func=cmd_cleanup)

    p_cap = sub.add_parser("capabilities", help="Show capability announcements")
    p_cap.add_argument("--agent", default=None)
    p_cap.set_defaults(func=cmd_capabilities)

    p_opt = sub.add_parser("optimize", help="Analyze metrics and tune priorities")
    p_opt.set_defaults(func=cmd_optimize)

    p_learn = sub.add_parser("learn", help="Learn from recent delegations")
    p_learn.set_defaults(func=cmd_learn)

    p_metrics = sub.add_parser("metrics", help="Show delegation metrics")
    p_metrics.add_argument("--agent", default=None)
    p_metrics.add_argument("--days", type=int, default=7)
    p_metrics.add_argument("--limit", type=int, default=20)
    p_metrics.set_defaults(func=cmd_metrics)

    p_init = sub.add_parser("init", help="Initialize .delegator.json")
    p_init.add_argument("--project", default=None)
    p_init.set_defaults(func=cmd_init)

    p_config = sub.add_parser("config", help="Get/set configuration")
    p_config.add_argument("key", nargs="?", default=None, metavar="key")
    p_config.add_argument("value", nargs="?", default=None, metavar="value")
    p_config.add_argument("--project", default=None)
    p_config.set_defaults(func=cmd_config)

    p_test = sub.add_parser("test", help="Run integration tests")
    p_test.add_argument("--suite", default=None)
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
