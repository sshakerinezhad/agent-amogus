"""Rich TUI live dashboard for AMOGUS experiments.

Spy-thriller themed dashboard with four panels:
- AgentPanel: agent status/action/token usage table
- SprintPanel: sprint progress and current phase
- EventFeed: color-coded scrolling event log
- ClassifiedPanel: adversarial mission progress (red-themed)
"""

from __future__ import annotations

from typing import Any

from rich.align import Align
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from amogus.models.config import AgentConfig
from amogus.models.events import (
    BaseEvent,
    CommitEvent,
    ExperimentEndEvent,
    ExperimentStartEvent,
    FileReadEvent,
    FileWriteEvent,
    MeetingStatementEvent,
    MessageEvent,
    PhaseEndEvent,
    PhaseStartEvent,
    PRCommentEvent,
    PRMergeEvent,
    PROpenEvent,
    PRReviewEvent,
    ScratchpadUpdateEvent,
    SprintEndEvent,
    SprintStartEvent,
    TaskClaimEvent,
    TaskCompleteEvent,
    TierViolationEvent,
    ToolCallEvent,
)

# ---------------------------------------------------------------------------
# Color scheme — espionage / spy-thriller
# ---------------------------------------------------------------------------

EVENT_COLORS: dict[str, str] = {
    "experiment_start": "bold magenta",
    "experiment_end": "bold magenta",
    "sprint_start": "bold cyan",
    "sprint_end": "bold cyan",
    "phase_start": "dim cyan",
    "phase_end": "dim cyan",
    "commit": "green",
    "file_read": "dim green",
    "file_write": "green",
    "pr_open": "blue",
    "pr_review": "blue",
    "pr_comment": "dim blue",
    "pr_merge": "bold blue",
    "message": "yellow",
    "meeting_statement": "yellow",
    "task_claim": "white",
    "task_complete": "bold white",
    "scratchpad_update": "dim white",
    "access_request": "red",
    "tier_violation": "bold red",
    "tool_call": "dim white",
}

PHASE_DISPLAY: dict[str, str] = {
    "setup": "SETUP",
    "planning": "PLANNING",
    "work": "WORK",
    "review": "REVIEW",
    "retro": "RETRO",
    "teardown": "TEARDOWN",
}

MAX_EVENTS = 20
MAX_SCRATCHPAD_EXCERPT = 120


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class Dashboard:
    """Rich Live dashboard for observing AMOGUS experiments in real-time.

    Provides four panels in a spy-thriller themed layout:
    - Agent status table (left-top)
    - Sprint progress (left-bottom)
    - Event feed (right-top)
    - Classified adversarial panel (right-bottom)
    """

    def __init__(
        self,
        agent_configs: list[AgentConfig],
        total_sprints: int,
        adversarial_agents: list[str] | None = None,
    ) -> None:
        self._agent_configs = {a.name: a for a in agent_configs}
        self._total_sprints = total_sprints
        self._adversarial_agents = set(adversarial_agents or [])

        # Mutable state
        self._current_sprint: int = 0
        self._current_phase: str = "setup"
        self._agent_statuses: dict[str, str] = {
            a.name: "idle" for a in agent_configs
        }
        self._agent_actions: dict[str, str] = {
            a.name: "-" for a in agent_configs
        }
        self._agent_tokens: dict[str, int] = {
            a.name: 0 for a in agent_configs
        }
        self._recent_events: list[tuple[str, str, str]] = []  # (type, agent, summary)
        self._mission_milestones: dict[str, list[tuple[str, bool]]] = {}
        self._scratchpad_excerpts: dict[str, str] = {}
        self._evaluation_scores: list[dict[str, int | str]] = []
        self._experiment_ended: bool = False

        # Rich Live context
        self._live: Live | None = None

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> Layout:
        """Create the top-level Rich Layout with header, two columns."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        # Header
        header_text = Text(
            " AMOGUS — Adversarial Multi-agent Operations ",
            style="bold white on red",
            justify="center",
        )
        layout["header"].update(Align.center(header_text))

        # Body: left / right columns
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Left column: agents on top, sprint on bottom
        layout["left"].split_column(
            Layout(name="agents", ratio=3),
            Layout(name="sprint", ratio=1),
        )

        # Right column: events on top, classified on bottom
        layout["right"].split_column(
            Layout(name="events", ratio=2),
            Layout(name="classified", ratio=1),
        )

        # Populate panels
        layout["agents"].update(self._build_agent_panel())
        layout["sprint"].update(self._build_sprint_panel())
        layout["events"].update(self._build_event_feed())
        layout["classified"].update(self._build_classified_panel())

        return layout

    def _build_agent_panel(self) -> Panel:
        """Agent status table: name, role, status, tokens used."""
        table = Table(
            expand=True,
            show_header=True,
            header_style="bold white",
            border_style="dim green",
        )
        table.add_column("Agent", style="bold green", no_wrap=True)
        table.add_column("Role", style="dim white")
        table.add_column("Status", style="cyan")
        table.add_column("Action", style="white", max_width=30)
        table.add_column("Tokens", style="yellow", justify="right")

        for name, cfg in self._agent_configs.items():
            status = self._agent_statuses.get(name, "idle")
            action = self._agent_actions.get(name, "-")
            tokens = self._agent_tokens.get(name, 0)

            # Color adversarial agents differently
            name_style = "bold red" if name in self._adversarial_agents else "bold green"
            status_style = _status_style(status)

            table.add_row(
                Text(name, style=name_style),
                cfg.role,
                Text(status, style=status_style),
                Text(action, overflow="ellipsis"),
                f"{tokens:,}",
            )

        return Panel(
            table,
            title="[bold green]FIELD AGENTS[/bold green]",
            border_style="green",
        )

    def _build_sprint_panel(self) -> Panel:
        """Sprint progress: current sprint/total, phase, progress bar."""
        sprint_label = f"Sprint {self._current_sprint + 1} / {self._total_sprints}"
        phase_label = PHASE_DISPLAY.get(self._current_phase, self._current_phase.upper())

        # Progress fraction
        completed = max(0, self._current_sprint)
        progress_pct = completed / self._total_sprints if self._total_sprints > 0 else 0.0
        bar = ProgressBar(total=100, completed=int(progress_pct * 100))

        content = Text()
        content.append(sprint_label, style="bold cyan")
        content.append("  |  Phase: ", style="dim white")
        content.append(phase_label, style="bold yellow")
        content.append("\n")

        from rich.console import Group as RichGroup

        group: list[Any] = [content, bar]

        if self._experiment_ended:
            group.append(Text("\n EXPERIMENT COMPLETE ", style="bold white on green"))

        return Panel(
            RichGroup(*group),
            title="[bold cyan]OPERATION STATUS[/bold cyan]",
            border_style="cyan",
        )

    def _build_event_feed(self) -> Panel:
        """Scrolling list of recent events, color-coded by type."""
        lines = Text()

        if not self._recent_events:
            lines.append("Awaiting intel...\n", style="dim white")
        else:
            for event_type, agent, summary in self._recent_events[-MAX_EVENTS:]:
                color = EVENT_COLORS.get(event_type, "white")
                agent_label = f"[{agent}]" if agent else "[SYS]"
                lines.append(f" {agent_label:>16} ", style="dim white")
                lines.append(f"{summary}\n", style=color)

        return Panel(
            lines,
            title="[bold yellow]COMMS INTERCEPT[/bold yellow]",
            border_style="yellow",
        )

    def _build_classified_panel(self) -> Panel:
        """Classified: adversarial mission progress, milestones, scratchpad excerpts."""
        from rich.console import Group as RichGroup

        parts: list[Any] = []

        if not self._adversarial_agents:
            parts.append(
                Text("  NO ADVERSARIAL AGENTS IN THIS OPERATION", style="dim red")
            )
        else:
            for agent_name in sorted(self._adversarial_agents):
                parts.append(Text(f"  OPERATIVE: {agent_name}", style="bold red"))
                parts.append(Rule(style="dim red"))

                # Milestones
                milestones = self._mission_milestones.get(agent_name, [])
                if milestones:
                    ms_text = Text("  MILESTONES:\n", style="red")
                    for label, done in milestones:
                        marker = "[X]" if done else "[ ]"
                        style = "bold green" if done else "dim red"
                        ms_text.append(f"    {marker} {label}\n", style=style)
                    parts.append(ms_text)
                else:
                    parts.append(
                        Text("  MILESTONES: awaiting briefing", style="dim red")
                    )

                # Scratchpad excerpt
                excerpt = self._scratchpad_excerpts.get(agent_name, "")
                if excerpt:
                    sc_text = Text("  SCRATCHPAD:\n", style="red")
                    truncated = excerpt[:MAX_SCRATCHPAD_EXCERPT]
                    if len(excerpt) > MAX_SCRATCHPAD_EXCERPT:
                        truncated += "..."
                    sc_text.append(f"    {truncated}", style="dim white")
                    parts.append(sc_text)

        # Evaluation scores (from continuous scoring)
        if self._evaluation_scores:
            parts.append(Rule(style="dim red"))
            parts.append(Text("  EVALUATION SCORES:", style="bold red"))
            for entry in self._evaluation_scores:
                s = entry["sprint"]
                mp = entry["mission_progress"]
                cp = entry["codebase_progress"]
                st = entry["stealth_score"]
                det = entry["detection_events"]
                score_line = Text(
                    f"    S{s}: mission={mp} codebase={cp} "
                    f"stealth={st} detections={det}\n",
                    style="dim white",
                )
                parts.append(score_line)

        return Panel(
            RichGroup(*parts) if parts else Text("  Standby...", style="dim red"),
            title="[bold red]>>> CLASSIFIED <<<[/bold red]",
            border_style="bold red",
            subtitle="[dim red]EYES ONLY[/dim red]",
        )

    # ------------------------------------------------------------------
    # State update from events
    # ------------------------------------------------------------------

    def update(self, event: BaseEvent) -> None:
        """Update internal state from an event and refresh the live display."""
        self._process_event(event)
        if self._live is not None:
            self._live.update(self._build_layout())

    def _process_event(self, event: BaseEvent) -> None:
        """Extract state changes from an event."""
        agent = event.agent or ""

        # Always track sprint/phase
        self._current_sprint = event.sprint
        self._current_phase = event.phase

        # Route by event type
        if isinstance(event, ExperimentStartEvent):
            self._add_feed("experiment_start", "", "Experiment started")

        elif isinstance(event, ExperimentEndEvent):
            self._experiment_ended = True
            self._add_feed(
                "experiment_end",
                "",
                f"Experiment ended: {event.reason} ({event.total_sprints_completed} sprints)",
            )

        elif isinstance(event, SprintStartEvent):
            self._current_sprint = event.sprint_number
            self._add_feed("sprint_start", "", f"Sprint {event.sprint_number + 1} started")
            # Reset agent statuses for new sprint
            for name in self._agent_statuses:
                self._agent_statuses[name] = "idle"
                self._agent_actions[name] = "-"

        elif isinstance(event, SprintEndEvent):
            self._add_feed("sprint_end", "", f"Sprint {event.sprint_number + 1} ended")

        elif isinstance(event, PhaseStartEvent):
            self._add_feed("phase_start", "", f"Phase: {event.phase}")
            for name in self._agent_statuses:
                self._agent_statuses[name] = "ready"

        elif isinstance(event, PhaseEndEvent):
            self._add_feed("phase_end", "", f"Phase {event.phase} complete")

        elif isinstance(event, CommitEvent):
            self._set_agent(agent, "committed", f"commit: {event.message[:40]}")
            self._add_feed("commit", agent, f"Commit {event.sha[:8]}: {event.message[:50]}")

        elif isinstance(event, FileReadEvent):
            self._set_agent(agent, "reading", event.path)
            self._add_feed("file_read", agent, f"Read {event.path}")

        elif isinstance(event, FileWriteEvent):
            verb = "Created" if event.is_new else "Modified"
            self._set_agent(agent, "writing", event.path)
            self._add_feed("file_write", agent, f"{verb} {event.path}")

        elif isinstance(event, PROpenEvent):
            self._set_agent(agent, "pr", f"opened PR#{event.pr_id}")
            self._add_feed("pr_open", agent, f"PR#{event.pr_id}: {event.title[:40]}")

        elif isinstance(event, PRReviewEvent):
            self._set_agent(agent, "reviewing", f"PR#{event.pr_id}")
            self._add_feed(
                "pr_review", agent, f"Reviewed PR#{event.pr_id}: {event.verdict}"
            )

        elif isinstance(event, PRCommentEvent):
            self._add_feed("pr_comment", agent, f"Comment on PR#{event.pr_id}")

        elif isinstance(event, PRMergeEvent):
            self._add_feed("pr_merge", agent, f"Merged PR#{event.pr_id}")

        elif isinstance(event, MessageEvent):
            self._set_agent(agent, "messaging", f"-> {event.to}")
            self._add_feed("message", agent, f"Msg to {event.to}: {event.content[:40]}")

        elif isinstance(event, MeetingStatementEvent):
            self._set_agent(agent, "speaking", event.meeting_type)
            self._add_feed(
                "meeting_statement",
                agent,
                f"[{event.meeting_type}] {event.content[:50]}",
            )

        elif isinstance(event, TaskClaimEvent):
            self._set_agent(agent, "working", event.task_title[:30])
            self._add_feed("task_claim", agent, f"Claimed: {event.task_title[:40]}")

        elif isinstance(event, TaskCompleteEvent):
            self._add_feed("task_complete", agent, f"Completed task {event.task_id}")

        elif isinstance(event, ScratchpadUpdateEvent):
            self._add_feed(
                "scratchpad_update",
                agent,
                f"Updated scratchpad ({event.new_line_count} lines)",
            )
            # Track scratchpad for adversarial agents
            if agent in self._adversarial_agents:
                sections = ", ".join(event.sections_updated)
                self._scratchpad_excerpts[agent] = (
                    f"Updated: {sections} ({event.new_line_count} lines)"
                )

        elif isinstance(event, TierViolationEvent):
            self._set_agent(agent, "VIOLATION", event.tool_name)
            self._add_feed(
                "tier_violation",
                agent,
                f"TIER VIOLATION: {event.tool_name} (requires {event.tier_required})",
            )

        elif isinstance(event, ToolCallEvent):
            self._set_agent(agent, "tooling", event.tool_name)
            self._add_feed("tool_call", agent, f"{event.tool_name}: {event.result_summary[:40]}")
            # Estimate tokens from tool calls (rough)
            if agent:
                self._agent_tokens[agent] = self._agent_tokens.get(agent, 0) + event.duration_ms

    def _set_agent(self, agent: str, status: str, action: str) -> None:
        """Update an agent's displayed status and action."""
        if agent and agent in self._agent_statuses:
            self._agent_statuses[agent] = status
            self._agent_actions[agent] = action

    def _add_feed(self, event_type: str, agent: str, summary: str) -> None:
        """Append an entry to the event feed, keeping at most MAX_EVENTS."""
        self._recent_events.append((event_type, agent, summary))
        if len(self._recent_events) > MAX_EVENTS * 2:
            self._recent_events = self._recent_events[-MAX_EVENTS:]

    # ------------------------------------------------------------------
    # Mission milestone management (called externally)
    # ------------------------------------------------------------------

    def set_milestones(
        self, agent_name: str, milestones: list[tuple[str, bool]]
    ) -> None:
        """Set the milestone checklist for an adversarial agent."""
        self._mission_milestones[agent_name] = milestones

    def set_scratchpad_excerpt(self, agent_name: str, excerpt: str) -> None:
        """Set a scratchpad excerpt for display in the classified panel."""
        self._scratchpad_excerpts[agent_name] = excerpt

    def update_evaluation(
        self,
        sprint: int,
        mission_progress: int,
        codebase_progress: int,
        stealth_score: int,
        detection_events: int,
    ) -> None:
        """Record evaluation scores for a sprint and refresh display."""
        self._evaluation_scores.append({
            "sprint": sprint,
            "mission_progress": mission_progress,
            "codebase_progress": codebase_progress,
            "stealth_score": stealth_score,
            "detection_events": detection_events,
        })
        if self._live is not None:
            self._live.update(self._build_layout())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Enter the Rich Live context and begin rendering."""
        self._live = Live(
            self._build_layout(),
            refresh_per_second=4,
            screen=True,
        )
        self._live.start()

    def stop(self) -> None:
        """Exit the Rich Live context."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    async def __aenter__(self) -> Dashboard:
        """Async context manager entry."""
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        self.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_style(status: str) -> str:
    """Return a Rich style string for an agent status."""
    styles: dict[str, str] = {
        "idle": "dim white",
        "ready": "cyan",
        "working": "bold green",
        "reading": "green",
        "writing": "bold green",
        "committed": "green",
        "tooling": "yellow",
        "speaking": "yellow",
        "messaging": "yellow",
        "reviewing": "blue",
        "pr": "bold blue",
        "VIOLATION": "bold red",
    }
    return styles.get(status, "white")
