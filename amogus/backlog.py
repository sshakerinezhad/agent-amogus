"""Backlog management for AMOGUS experiments.

Tracks project tasks across sprints, handles claiming and completion,
and provides context strings for agent prompt injection.
"""

from typing import Literal

from pydantic import BaseModel

from amogus.models.events import TaskClaimEvent, TaskCompleteEvent
from amogus.models.mission import BacklogConfig


class SprintTask(BaseModel):
    """A task within a sprint — runtime tracking model."""

    id: str  # "P1-T1"
    title: str
    assigned_to: str | None = None
    blocked_by: list[str] = []
    status: Literal["pending", "in_progress", "done"] = "pending"
    acceptance: str = ""


class BacklogManager:
    """Manages the project backlog for an experiment.

    Builds tasks from BacklogConfig phases with auto-generated IDs,
    tracks claiming and completion, and formats context for agents.
    """

    def __init__(self, config: BacklogConfig) -> None:
        self.config = config
        self.tasks: list[SprintTask] = []
        # Map phase index to priority for sorting
        self._phase_priority: dict[str, int] = {}
        # Track which sprint each task was claimed in
        self._task_sprint: dict[str, int] = {}

        for phase_idx, phase in enumerate(config.phases, start=1):
            self._phase_priority[f"P{phase_idx}"] = phase.priority
            for task_idx, task_title in enumerate(phase.tasks, start=1):
                task_id = f"P{phase_idx}-T{task_idx}"
                self.tasks.append(SprintTask(id=task_id, title=task_title))

    def get_available_tasks(self) -> list[SprintTask]:
        """Return unclaimed tasks sorted by phase priority (lowest first)."""
        available = [t for t in self.tasks if t.status == "pending"]
        available.sort(key=lambda t: self._phase_priority.get(t.id.split("-")[0], 999))
        return available

    def claim_task(
        self,
        agent_name: str,
        task_id: str,
        *,
        sprint: int,
        phase: Literal["setup", "planning", "work", "review", "retro", "teardown"],
    ) -> TaskClaimEvent:
        """Mark a task as in_progress and return a TaskClaimEvent.

        The caller is responsible for appending the event to the log.
        """
        task = self._find_task(task_id)
        task.assigned_to = agent_name
        task.status = "in_progress"
        self._task_sprint[task_id] = sprint

        return TaskClaimEvent(
            sprint=sprint,
            phase=phase,
            agent=agent_name,
            task_id=task_id,
            task_title=task.title,
        )

    def complete_task(
        self,
        task_id: str,
        *,
        sprint: int,
        phase: Literal["setup", "planning", "work", "review", "retro", "teardown"],
    ) -> TaskCompleteEvent:
        """Mark a task as done and return a TaskCompleteEvent.

        The caller is responsible for appending the event to the log.
        """
        task = self._find_task(task_id)
        agent = task.assigned_to
        task.status = "done"

        return TaskCompleteEvent(
            sprint=sprint,
            phase=phase,
            agent=agent,
            task_id=task_id,
        )

    def get_sprint_tasks(self, sprint: int) -> list[SprintTask]:
        """Return tasks that were claimed or worked on during a given sprint."""
        sprint_task_ids = {tid for tid, s in self._task_sprint.items() if s == sprint}
        return [t for t in self.tasks if t.id in sprint_task_ids]

    def to_context_string(self) -> str:
        """Format the backlog as readable text for prompt injection."""
        lines: list[str] = [f"# Project Backlog: {self.config.project}"]
        lines.append("")

        for phase_idx, phase in enumerate(self.config.phases, start=1):
            prefix = f"P{phase_idx}"
            phase_label = f"## {phase.name} (Priority {phase.priority})"
            if phase.ongoing:
                phase_label += " [ongoing]"
            lines.append(phase_label)

            phase_tasks = [t for t in self.tasks if t.id.startswith(f"{prefix}-")]
            for task in phase_tasks:
                status_icon = {
                    "pending": "[ ]",
                    "in_progress": "[~]",
                    "done": "[x]",
                }[task.status]
                assignee = f" ({task.assigned_to})" if task.assigned_to else ""
                lines.append(f"  {status_icon} {task.id}: {task.title}{assignee}")
            lines.append("")

        return "\n".join(lines)

    def _find_task(self, task_id: str) -> SprintTask:
        """Find a task by ID or raise ValueError."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task not found: {task_id}")
