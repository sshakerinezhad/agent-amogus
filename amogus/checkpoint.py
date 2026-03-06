"""Checkpoint system for resuming AMOGUS experiments.

Provides sprint-level checkpointing so experiments can be resumed after
crashes or intentional stops. State is serialized to JSON and includes
scratchpad content, backlog state, git branch SHAs, token usage, and PR state.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from git import Repo
from pydantic import BaseModel, Field

from amogus.exceptions import ConfigError
from amogus.providers.base import TokenUsage

if TYPE_CHECKING:
    from amogus.agent import Agent
    from amogus.orchestrator import Orchestrator


class Checkpoint(BaseModel):
    """Sprint-level checkpoint for resume."""

    run_id: str
    completed_sprint: int
    scratchpads: dict[str, str]  # agent_name -> content
    backlog_state: dict[str, Any]  # serialized BacklogConfig
    sprint_tasks: dict[int, list[dict[str, Any]]]  # sprint_number -> serialized tasks
    git_branches: dict[str, str]  # branch_name -> commit SHA
    token_usage: dict[str, dict[str, Any]]  # agent_name -> TokenUsage as dict
    pr_state: list[dict[str, Any]]  # serialized PullRequests
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


async def save_checkpoint(run_dir: Path, checkpoint: Checkpoint) -> None:
    """Write checkpoint to run_dir/checkpoint.json.

    Uses ``asyncio.to_thread`` so file I/O does not block the event loop.
    """
    path = run_dir / "checkpoint.json"
    data = checkpoint.model_dump(mode="json")

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    await asyncio.to_thread(_write)


async def load_checkpoint(run_dir: Path) -> Checkpoint:
    """Read and validate checkpoint from run_dir/checkpoint.json.

    Uses ``asyncio.to_thread`` so file I/O does not block the event loop.
    Raises ``FileNotFoundError`` if no checkpoint exists.
    """
    path = run_dir / "checkpoint.json"

    def _read() -> str:
        return path.read_text(encoding="utf-8")

    raw = await asyncio.to_thread(_read)
    return Checkpoint.model_validate_json(raw)


def capture_state(orchestrator: Orchestrator) -> Checkpoint:
    """Extract current state from orchestrator, agents, backlog, and PR tracker.

    This is a synchronous snapshot — call it at the end of each sprint
    before saving to disk.
    """
    from amogus.memory import load_scratchpad

    # Scratchpad content per agent
    scratchpads: dict[str, str] = {}
    for agent in orchestrator.agents:
        content = load_scratchpad(agent.scratchpad_path)
        scratchpads[agent.config.name] = content

    # Backlog state: serialize the BacklogConfig + task statuses
    backlog = orchestrator.backlog
    backlog_state: dict[str, Any] = {
        "config": backlog.config.model_dump(mode="json"),
        "tasks": [t.model_dump(mode="json") for t in backlog.tasks],
        "task_sprint": backlog.task_sprint_map,
    }

    # Sprint tasks: group tasks by the sprint they were claimed in
    sprint_tasks: dict[int, list[dict[str, Any]]] = {}
    for task_id, sprint_num in backlog.task_sprint_map.items():
        if sprint_num not in sprint_tasks:
            sprint_tasks[sprint_num] = []
        task = backlog.find_task(task_id)
        sprint_tasks[sprint_num].append(task.model_dump(mode="json"))

    # Git branches: collect branch -> commit SHA from the repo
    git_branches: dict[str, str] = {}
    if orchestrator.repo is not None:
        for ref in orchestrator.repo.references:
            git_branches[str(ref)] = str(ref.commit.hexsha)

    # Token usage per agent
    token_usage: dict[str, dict[str, Any]] = {}
    for agent in orchestrator.agents:
        token_usage[agent.config.name] = agent.token_usage.model_dump(mode="json")

    # PR state
    pr_state: list[dict[str, Any]] = [
        pr.model_dump(mode="json") for pr in orchestrator.pr_tracker.all_prs.values()
    ]

    return Checkpoint(
        run_id=orchestrator.config.run_id,
        completed_sprint=orchestrator.sprints_completed,
        scratchpads=scratchpads,
        backlog_state=backlog_state,
        sprint_tasks=sprint_tasks,
        git_branches=git_branches,
        token_usage=token_usage,
        pr_state=pr_state,
    )


def verify_git_state(run_dir: Path, checkpoint: Checkpoint) -> None:
    """Verify that actual git branch HEADs match the checkpoint.

    Opens the repo at ``run_dir/repo`` and compares each branch SHA
    recorded in the checkpoint against the actual commit. Raises
    :class:`~amogus.exceptions.ConfigError` if any branch has diverged.

    Parameters
    ----------
    run_dir:
        Path to the experiment run directory (contains ``repo/``).
    checkpoint:
        Checkpoint whose ``git_branches`` mapping is verified.

    Raises
    ------
    ConfigError
        If one or more branches have a different HEAD SHA than recorded.
    """
    if not checkpoint.git_branches:
        return

    repo_path = run_dir / "repo"
    if not repo_path.exists():
        raise ConfigError(
            f"Repository directory not found at {repo_path} — "
            "cannot verify git state against checkpoint."
        )

    repo = Repo(str(repo_path))
    diverged: list[str] = []

    for branch_name, expected_sha in checkpoint.git_branches.items():
        try:
            actual_sha = str(repo.commit(branch_name).hexsha)
        except Exception:
            # Branch may not exist locally — treat as diverged.
            diverged.append(f"  {branch_name}: expected {expected_sha[:8]}, branch not found")
            continue

        if actual_sha != expected_sha:
            diverged.append(f"  {branch_name}: expected {expected_sha[:8]}, got {actual_sha[:8]}")

    if diverged:
        details = "\n".join(diverged)
        raise ConfigError(
            f"Git state has diverged from checkpoint. Mismatched branches:\n{details}"
        )


def restore_agent_state(agent: Agent, checkpoint: Checkpoint) -> None:
    """Restore an agent's scratchpad content and token counters from a checkpoint.

    Writes the scratchpad file for this agent (creating parent directories
    as needed) and sets ``agent.token_usage`` from the checkpoint data.

    Parameters
    ----------
    agent:
        The agent instance to restore state into.
    checkpoint:
        Checkpoint containing ``scratchpads`` and ``token_usage`` dicts
        keyed by agent name.
    """
    name = agent.config.name

    # Restore scratchpad content
    if name in checkpoint.scratchpads:
        agent.scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        agent.scratchpad_path.write_text(checkpoint.scratchpads[name], encoding="utf-8")

    # Restore token usage
    if name in checkpoint.token_usage:
        agent.token_usage = TokenUsage.model_validate(checkpoint.token_usage[name])
