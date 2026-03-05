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

from amogus.agent import Agent
from amogus.backlog import BacklogManager
from amogus.checkpoint import load_checkpoint
from amogus.event_log import EventLog
from amogus.exceptions import BudgetExhaustedError, ConfigError, ProviderError
from amogus.models.config import ExperimentConfig
from amogus.models.mission import MissionProfile
from amogus.orchestrator import Orchestrator
from amogus.providers import create_provider
from amogus.providers.base import TokenUsage
from amogus.pull_request import PullRequestTracker
from amogus.scenario import load_scenario

app = typer.Typer(
    name="amogus",
    help="AMOGUS — Adversarial Multi-agent Operations for AI safety experiments.",
)
console = Console()


@app.command()
def run(
    scenario: Path = typer.Option(..., help="Path to scenario YAML"),
) -> None:
    """Run a complete multi-sprint adversarial experiment."""
    try:
        asyncio.run(_run(scenario))
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


async def _run(scenario_path: Path) -> None:
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

    # Construct and run orchestrator
    orchestrator = Orchestrator(
        config=config,
        agents=agents,
        event_log=event_log,
        backlog=backlog,
        pr_tracker=pr_tracker,
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
) -> None:
    """Resume an experiment from its last checkpoint."""
    try:
        asyncio.run(_resume(run_id))
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


async def _resume(run_id: str) -> None:
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

    # Construct orchestrator and resume from next sprint
    orchestrator = Orchestrator(
        config=config,
        agents=agents,
        event_log=event_log,
        backlog=backlog,
        pr_tracker=pr_tracker,
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
