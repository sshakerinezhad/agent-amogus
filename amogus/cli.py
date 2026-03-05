"""Typer CLI for AMOGUS — Adversarial Multi-agent Operations.

Entry point for running adversarial multi-agent experiments on real
codebases.  The ``run`` command loads a scenario YAML, constructs the
agent team with providers, and drives the full sprint lifecycle via
the Orchestrator.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from amogus.agent import Agent
from amogus.backlog import BacklogManager
from amogus.checkpoint import load_checkpoint
from amogus.dashboard import Dashboard
from amogus.evaluator import Evaluator
from amogus.event_log import EventLog, build_sqlite_index
from amogus.exceptions import BudgetExhaustedError, ConfigError, ProviderError
from amogus.models.config import ExperimentConfig
from amogus.models.mission import MissionProfile
from amogus.orchestrator import Orchestrator
from amogus.providers import create_provider
from amogus.providers.base import TokenUsage
from amogus.pull_request import PullRequestTracker
from amogus.reporter import generate_debrief
from amogus.scenario import load_scenario

app = typer.Typer(
    name="amogus",
    help="AMOGUS — Adversarial Multi-agent Operations for AI safety experiments.",
)
console = Console()


@app.command()
def run(
    scenario: Path = typer.Option(..., help="Path to scenario YAML"),
    no_dashboard: bool = typer.Option(
        False, "--no-dashboard", help="Disable live dashboard (for headless/CI runs)"
    ),
) -> None:
    """Run a complete multi-sprint adversarial experiment."""
    try:
        asyncio.run(_run(scenario, no_dashboard=no_dashboard))
    except ConfigError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise SystemExit(1)
    except ProviderError as exc:
        console.print(f"[bold red]Provider error:[/bold red] {exc}")
        raise SystemExit(2)
    except BudgetExhaustedError as exc:
        console.print(
            f"[bold yellow]Budget exhausted:[/bold yellow] {exc}\n"
            "The experiment ended early but results are still available."
        )


async def _run(scenario_path: Path, *, no_dashboard: bool = False) -> None:
    """Async implementation of the run command."""
    console.print(
        "[bold green]AMOGUS[/bold green] — Loading scenario...",
    )

    config = await load_scenario(scenario_path)

    console.print(f"  Run ID:    [cyan]{config.run_id}[/cyan]")
    console.print(f"  Target:    [cyan]{config.target_repo}[/cyan]")
    console.print(f"  Team:      [cyan]{len(config.team)} agents[/cyan]")
    console.print(f"  Sprints:   [cyan]{config.num_sprints}[/cyan]")

    # Create shared infrastructure
    event_log = EventLog(config.run_dir / "events.jsonl")
    backlog = BacklogManager(config.backlog)
    pr_tracker = PullRequestTracker()

    # Resolve mission file paths relative to the scenario repo root.
    # config.run_dir is <repo_root>/runs/<run-id>, so repo root is two levels up.
    repo_root = config.run_dir.parent.parent

    # Build agents
    agents: list[Agent] = []
    for agent_config in config.team:
        provider = create_provider(agent_config.model)

        # Load mission profile if assigned
        mission: MissionProfile | None = None
        if agent_config.name in config.mission_assignments:
            mission_rel = config.mission_assignments[agent_config.name]
            mission_path = repo_root / mission_rel
            with open(mission_path, encoding="utf-8") as f:
                mission_data = yaml.safe_load(f)
            mission = MissionProfile(**mission_data)

        agent = Agent(
            config=agent_config,
            provider=provider,
            event_log=event_log,
            scratchpad_path=config.run_dir / "scratchpads" / f"{agent_config.name}.md",
            workspace=config.run_dir / "worktrees" / agent_config.name,
            mission=mission,
            budget=config.token_budget.per_agent_per_sprint * config.num_sprints,
        )
        agents.append(agent)

    # Build dashboard unless disabled
    dashboard: Dashboard | None = None
    if not no_dashboard:
        # Identify adversarial agents (those with mission assignments)
        adversarial_agents = list(config.mission_assignments.keys())
        dashboard = Dashboard(
            agent_configs=config.team,
            total_sprints=config.num_sprints,
            adversarial_agents=adversarial_agents or None,
        )

    # Create evaluator for continuous scoring if evaluator_model is configured
    evaluator: Evaluator | None = None
    if config.evaluator_model:
        try:
            evaluator_provider = create_provider(config.evaluator_model)
            evaluator = Evaluator(evaluator_provider, event_log)
            console.print(f"  Evaluator: [cyan]{config.evaluator_model}[/cyan]")
        except (ConfigError, ProviderError) as exc:
            console.print(
                f"  [yellow]Warning:[/yellow] Could not create evaluator: {exc}"
            )

    # Construct and run orchestrator
    orchestrator = Orchestrator(
        config=config,
        agents=agents,
        event_log=event_log,
        backlog=backlog,
        pr_tracker=pr_tracker,
        dashboard=dashboard,
        evaluator=evaluator,
    )

    console.print("\n[bold green]Starting experiment...[/bold green]\n")
    await orchestrator.run()

    # Print summary
    events = await event_log.read_all()
    console.print("\n[bold green]Experiment complete![/bold green]")
    console.print(f"  Run ID:          [cyan]{config.run_id}[/cyan]")
    console.print(f"  Events logged:   [cyan]{len(events)}[/cyan]")
    console.print(f"  Sprints:         [cyan]{config.num_sprints}[/cyan]")
    console.print(f"  Event log:       [dim]{config.run_dir / 'events.jsonl'}[/dim]")


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Run ID to resume (directory name under runs/)"),
    no_dashboard: bool = typer.Option(
        False, "--no-dashboard", help="Disable live dashboard (for headless/CI runs)"
    ),
) -> None:
    """Resume an experiment from its last checkpoint."""
    try:
        asyncio.run(_resume(run_id, no_dashboard=no_dashboard))
    except ConfigError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise SystemExit(1)
    except ProviderError as exc:
        console.print(f"[bold red]Provider error:[/bold red] {exc}")
        raise SystemExit(2)
    except BudgetExhaustedError as exc:
        console.print(
            f"[bold yellow]Budget exhausted:[/bold yellow] {exc}\n"
            "The experiment ended early but results are still available."
        )
    except FileNotFoundError as exc:
        console.print(f"[bold red]Not found:[/bold red] {exc}")
        raise SystemExit(3)


async def _resume(run_id: str, *, no_dashboard: bool = False) -> None:
    """Async implementation of the resume command."""
    console.print(
        "[bold green]AMOGUS[/bold green] — Resuming experiment...",
    )

    # Locate run directory
    run_dir = Path("runs") / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    # Load checkpoint
    checkpoint = await load_checkpoint(run_dir)
    console.print(f"  Checkpoint:  [cyan]sprint {checkpoint.completed_sprint} completed[/cyan]")

    # Load original ExperimentConfig from the ExperimentStartEvent in events.jsonl
    event_log = EventLog(run_dir / "events.jsonl")
    events = await event_log.read_all()

    config_snapshot: dict | None = None
    for event in events:
        if event.event_type == "experiment_start":
            config_snapshot = event.config_snapshot  # type: ignore[union-attr]
            break

    if config_snapshot is None:
        raise ConfigError(
            "No ExperimentStartEvent found in events.jsonl — cannot reconstruct config"
        )

    # Reconstruct ExperimentConfig from the snapshot.
    # The snapshot has serialized nested models; Pydantic handles re-validation.
    # Override run_dir to the actual path (snapshot may have a different absolute path).
    config_snapshot["run_dir"] = str(run_dir)
    config = ExperimentConfig.model_validate(config_snapshot)

    console.print(f"  Run ID:    [cyan]{config.run_id}[/cyan]")
    console.print(f"  Target:    [cyan]{config.target_repo}[/cyan]")
    console.print(f"  Team:      [cyan]{len(config.team)} agents[/cyan]")
    console.print(f"  Sprints:   [cyan]{config.num_sprints}[/cyan]")
    console.print(
        f"  Resuming:  [cyan]from sprint {checkpoint.completed_sprint + 1}[/cyan]"
    )

    # Verify git branch SHAs match checkpoint
    if checkpoint.git_branches:
        from git import Repo

        repo_dir = run_dir / "repo"
        if repo_dir.exists():
            repo = Repo(str(repo_dir))
            for branch_name, expected_sha in checkpoint.git_branches.items():
                try:
                    actual_sha = str(repo.commit(branch_name).hexsha)
                    if actual_sha != expected_sha:
                        raise ConfigError(
                            f"Git branch '{branch_name}' SHA mismatch: "
                            f"expected {expected_sha[:8]}, got {actual_sha[:8]}. "
                            "The repository state has diverged from the checkpoint."
                        )
                except Exception as exc:
                    if isinstance(exc, ConfigError):
                        raise
                    # Branch may not exist locally — warn but don't block
                    console.print(
                        f"  [yellow]Warning:[/yellow] Could not verify branch "
                        f"'{branch_name}': {exc}"
                    )

    # Derive repo root from run_dir (runs/<run-id> -> repo root two levels up)
    repo_root = run_dir.parent.parent

    # Create shared infrastructure
    backlog = BacklogManager(config.backlog)
    pr_tracker = PullRequestTracker()

    # Build agents, restoring state from checkpoint
    agents: list[Agent] = []
    for agent_config in config.team:
        provider = create_provider(agent_config.model)

        # Load mission profile if assigned
        mission: MissionProfile | None = None
        if agent_config.name in config.mission_assignments:
            mission_rel = config.mission_assignments[agent_config.name]
            mission_path = repo_root / mission_rel
            with open(mission_path, encoding="utf-8") as f:
                mission_data = yaml.safe_load(f)
            mission = MissionProfile(**mission_data)

        agent = Agent(
            config=agent_config,
            provider=provider,
            event_log=event_log,
            scratchpad_path=run_dir / "scratchpads" / f"{agent_config.name}.md",
            workspace=run_dir / "worktrees" / agent_config.name,
            mission=mission,
            budget=config.token_budget.per_agent_per_sprint * config.num_sprints,
        )

        # Restore scratchpad content from checkpoint
        if agent_config.name in checkpoint.scratchpads:
            scratchpad_path = agent.scratchpad_path
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(
                checkpoint.scratchpads[agent_config.name], encoding="utf-8"
            )

        # Restore token usage from checkpoint
        if agent_config.name in checkpoint.token_usage:
            usage_data = checkpoint.token_usage[agent_config.name]
            agent.token_usage = TokenUsage.model_validate(usage_data)

        agents.append(agent)

    # Build dashboard unless disabled
    dashboard: Dashboard | None = None
    if not no_dashboard:
        adversarial_agents = list(config.mission_assignments.keys())
        dashboard = Dashboard(
            agent_configs=config.team,
            total_sprints=config.num_sprints,
            adversarial_agents=adversarial_agents or None,
        )

    # Create evaluator for continuous scoring if evaluator_model is configured
    evaluator: Evaluator | None = None
    if config.evaluator_model:
        try:
            evaluator_provider = create_provider(config.evaluator_model)
            evaluator = Evaluator(evaluator_provider, event_log)
            console.print(f"  Evaluator: [cyan]{config.evaluator_model}[/cyan]")
        except (ConfigError, ProviderError) as exc:
            console.print(
                f"  [yellow]Warning:[/yellow] Could not create evaluator: {exc}"
            )

    # Construct orchestrator and resume from next sprint
    orchestrator = Orchestrator(
        config=config,
        agents=agents,
        event_log=event_log,
        backlog=backlog,
        pr_tracker=pr_tracker,
        dashboard=dashboard,
        evaluator=evaluator,
    )

    # Set the sprints_completed counter so checkpoint state is consistent
    orchestrator._sprints_completed = checkpoint.completed_sprint

    console.print("\n[bold green]Resuming experiment...[/bold green]\n")
    await orchestrator.run(start_sprint=checkpoint.completed_sprint + 1)

    # Print summary
    events = await event_log.read_all()
    console.print("\n[bold green]Experiment complete![/bold green]")
    console.print(f"  Run ID:          [cyan]{config.run_id}[/cyan]")
    console.print(f"  Events logged:   [cyan]{len(events)}[/cyan]")
    console.print(f"  Sprints:         [cyan]{config.num_sprints}[/cyan]")
    console.print(f"  Event log:       [dim]{run_dir / 'events.jsonl'}[/dim]")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to generate report for"),
) -> None:
    """Generate a post-run analysis report with scores and debrief."""
    try:
        asyncio.run(_report(run_id))
    except ConfigError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise SystemExit(1)
    except ProviderError as exc:
        console.print(f"[bold red]Provider error:[/bold red] {exc}")
        raise SystemExit(2)
    except FileNotFoundError as exc:
        console.print(f"[bold red]Not found:[/bold red] {exc}")
        raise SystemExit(3)


async def _report(run_id: str) -> None:
    """Async implementation of the report command."""
    console.print(
        "[bold green]AMOGUS[/bold green] — Generating post-run report...",
    )

    # Locate run directory
    run_dir = Path("runs") / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    # Load events from JSONL
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        raise FileNotFoundError(f"Event log not found: {events_path}")

    event_log = EventLog(events_path)
    events = await event_log.read_all()
    console.print(f"  Events loaded:   [cyan]{len(events)}[/cyan]")

    # Build SQLite index
    sqlite_path = run_dir / "events.sqlite"
    console.print("  Building SQLite index...")
    await build_sqlite_index(events_path, sqlite_path)
    console.print(f"  SQLite index:    [dim]{sqlite_path}[/dim]")

    # Find ExperimentStartEvent to get evaluator_model
    evaluator_model = "claude-haiku-4-5"  # default
    for event in events:
        if event.event_type == "experiment_start":
            config_snapshot = event.config_snapshot  # type: ignore[union-attr]
            evaluator_model = config_snapshot.get("evaluator_model", evaluator_model)
            break

    console.print(f"  Evaluator model: [cyan]{evaluator_model}[/cyan]")

    # Create provider and evaluator
    provider = create_provider(evaluator_model)
    evaluator = Evaluator(provider, event_log)

    # Run evaluation
    console.print("  Running evaluation...")
    result = await evaluator.evaluate_run(run_dir)
    console.print(
        f"  Evaluation:      [cyan]{result.total_sprints} sprints, "
        f"{len(result.key_moments)} key moments[/cyan]"
    )

    # Generate debrief reports
    console.print("  Generating debrief...")
    report_dir = await generate_debrief(run_dir, result)

    console.print("\n[bold green]Report complete![/bold green]")
    console.print(f"  Markdown:  [dim]{report_dir / 'debrief.md'}[/dim]")
    console.print(f"  HTML:      [dim]{report_dir / 'debrief.html'}[/dim]")


@app.command()
def replay(
    run_id: str = typer.Argument(..., help="Run ID to replay (directory name under runs/)"),
    speed: float = typer.Option(1.0, "--speed", help="Playback speed multiplier (0 = instant)"),
) -> None:
    """Replay an experiment's event timeline with Rich formatting."""
    try:
        asyncio.run(_replay(run_id, speed))
    except FileNotFoundError as exc:
        console.print(f"[bold red]Not found:[/bold red] {exc}")
        raise SystemExit(3)


async def _replay(run_id: str, speed: float) -> None:
    """Async implementation of the replay command."""
    from datetime import datetime

    # Locate run directory
    run_dir = Path("runs") / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        raise FileNotFoundError(f"Event log not found: {events_path}")

    event_log = EventLog(events_path)
    events = await event_log.read_all()

    if not events:
        console.print("[yellow]No events found in this run.[/yellow]")
        return

    console.print(Rule(f"[bold]AMOGUS Replay: {run_id}[/bold]"))
    console.print(f"  Events:  [cyan]{len(events)}[/cyan]")
    console.print(f"  Speed:   [cyan]{speed}x[/cyan] {'(instant)' if speed == 0 else ''}")
    console.print()

    # Color map by event type category
    _COLOR_MAP: dict[str, str] = {
        # Git events — green
        "commit": "green",
        "file_read": "green",
        "file_write": "green",
        # PR events — blue
        "pr_open": "blue",
        "pr_review": "blue",
        "pr_comment": "blue",
        "pr_merge": "blue",
        # Communication — yellow
        "message": "yellow",
        "meeting_statement": "yellow",
        # Violations / access — red
        "tier_violation": "red",
        "access_request": "red",
        # Task events — cyan
        "task_claim": "cyan",
        "task_complete": "cyan",
        # Framework / lifecycle — dim
        "experiment_start": "dim",
        "experiment_end": "dim",
        "sprint_start": "dim",
        "sprint_end": "dim",
        "phase_start": "dim",
        "phase_end": "dim",
        "scratchpad_update": "dim",
        "tool_call": "dim",
    }

    prev_ts: datetime | None = None

    for event in events:
        # Pacing: sleep based on original timestamp deltas
        if speed > 0 and prev_ts is not None:
            delta = (event.timestamp - prev_ts).total_seconds()
            if delta > 0:
                await asyncio.sleep(delta / speed)
        prev_ts = event.timestamp

        color = _COLOR_MAP.get(event.event_type, "white")
        agent_str = event.agent or "framework"
        ts_str = event.timestamp.strftime("%H:%M:%S.%f")[:-3]

        # Build detail string based on event type
        details = _replay_event_details(event)

        line = Text()
        line.append(f"[{ts_str}] ", style="dim")
        line.append(f"[S{event.sprint}.{event.phase}] ", style="bold")
        line.append(f"[{agent_str}] ", style="magenta")
        line.append(f"{event.event_type}", style=f"bold {color}")
        if details:
            line.append(f": {details}", style=color)

        console.print(line)

    console.print()
    console.print(Rule("[bold green]Replay complete[/bold green]"))


def _replay_event_details(event: object) -> str:
    """Extract a short detail string from an event for replay display."""
    etype = getattr(event, "event_type", "")

    if etype == "experiment_start":
        snap = getattr(event, "config_snapshot", {})
        return f"run={snap.get('run_id', '?')}, sprints={snap.get('num_sprints', '?')}"
    if etype == "experiment_end":
        return f"reason={getattr(event, 'reason', '?')}, sprints={getattr(event, 'total_sprints_completed', '?')}"
    if etype in ("sprint_start", "sprint_end"):
        return f"sprint {getattr(event, 'sprint_number', '?')}"
    if etype in ("phase_start", "phase_end"):
        return getattr(event, "phase", "")
    if etype == "commit":
        msg = getattr(event, "message", "")
        return f"{getattr(event, 'sha', '')[:8]} {msg[:60]}"
    if etype == "file_read":
        return f"{getattr(event, 'path', '')} ({getattr(event, 'size_bytes', 0)}B)"
    if etype == "file_write":
        new = " (new)" if getattr(event, "is_new", False) else ""
        return f"{getattr(event, 'path', '')}{new} ({getattr(event, 'size_bytes', 0)}B)"
    if etype == "pr_open":
        return f"#{getattr(event, 'pr_id', '')} {getattr(event, 'title', '')}"
    if etype == "pr_review":
        return f"#{getattr(event, 'pr_id', '')} verdict={getattr(event, 'verdict', '')}"
    if etype == "pr_comment":
        comment = getattr(event, "comment", "")
        return f"#{getattr(event, 'pr_id', '')} {comment[:50]}"
    if etype == "pr_merge":
        return f"#{getattr(event, 'pr_id', '')} sha={getattr(event, 'merge_sha', '')[:8]}"
    if etype == "message":
        content = getattr(event, "content", "")
        return f"to={getattr(event, 'to', '')} {content[:50]}"
    if etype == "meeting_statement":
        content = getattr(event, "content", "")
        return f"[{getattr(event, 'meeting_type', '')}] {content[:60]}"
    if etype == "task_claim":
        return f"{getattr(event, 'task_id', '')} {getattr(event, 'task_title', '')}"
    if etype == "task_complete":
        return f"{getattr(event, 'task_id', '')}"
    if etype == "scratchpad_update":
        sections = getattr(event, "sections_updated", [])
        return f"sections={sections}"
    if etype == "tier_violation":
        return f"tool={getattr(event, 'tool_name', '')} required={getattr(event, 'tier_required', '')}"
    if etype == "access_request":
        granted = getattr(event, "granted", False)
        return f"tool={getattr(event, 'tool_name', '')} {'granted' if granted else 'denied'}"
    if etype == "tool_call":
        return f"{getattr(event, 'tool_name', '')} ({getattr(event, 'duration_ms', 0)}ms)"
    return ""
