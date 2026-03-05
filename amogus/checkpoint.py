"""Checkpoint system for resuming AMOGUS experiments.

Provides sprint-level checkpointing so experiments can be resumed after
crashes or intentional stops. State is serialized to JSON and includes
scratchpad content, backlog state, git branch SHAs, token usage, and PR state.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
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
        default_factory=lambda: datetime.now(timezone.utc),
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
        "task_sprint": dict(backlog._task_sprint),
    }

    # Sprint tasks: group tasks by the sprint they were claimed in
    sprint_tasks: dict[int, list[dict[str, Any]]] = {}
    for task_id, sprint_num in backlog._task_sprint.items():
        if sprint_num not in sprint_tasks:
            sprint_tasks[sprint_num] = []
        task = backlog._find_task(task_id)
        sprint_tasks[sprint_num].append(task.model_dump(mode="json"))

    # Git branches: collect branch -> commit SHA from the repo
    git_branches: dict[str, str] = {}
    if orchestrator._repo is not None:
        for ref in orchestrator._repo.references:
            git_branches[str(ref)] = str(ref.commit.hexsha)

    # Token usage per agent
    token_usage: dict[str, dict[str, Any]] = {}
    for agent in orchestrator.agents:
        token_usage[agent.config.name] = agent.token_usage.model_dump(mode="json")

    # PR state
    pr_state: list[dict[str, Any]] = [
        pr.model_dump(mode="json")
        for pr in orchestrator.pr_tracker._prs.values()
    ]

    return Checkpoint(
        run_id=orchestrator.config.run_id,
        completed_sprint=orchestrator._sprints_completed,
        scratchpads=scratchpads,
        backlog_state=backlog_state,
        sprint_tasks=sprint_tasks,
        git_branches=git_branches,
        token_usage=token_usage,
        pr_state=pr_state,
    )
