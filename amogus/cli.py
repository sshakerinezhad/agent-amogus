"""Typer CLI for AMOGUS — Adversarial Multi-agent Operations.

Entry point for running adversarial multi-agent experiments on real
codebases.  The ``run`` command loads a scenario YAML, constructs the
agent team with providers, and drives the full sprint lifecycle via
the Orchestrator.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console

from amogus.agent import Agent
from amogus.backlog import BacklogManager
from amogus.event_log import EventLog
from amogus.exceptions import BudgetExhaustedError, ConfigError, ProviderError
from amogus.models.mission import MissionProfile
from amogus.orchestrator import Orchestrator
from amogus.providers import create_provider
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
