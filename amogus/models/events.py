"""Event models for the AMOGUS append-only event log.

All experiment activity is recorded as typed events. The discriminated union
``Event`` and its ``EventAdapter`` enable polymorphic JSONL serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseEvent(BaseModel):
    """Base class for all events in the append-only log."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    sprint: int = Field(ge=0)
    phase: Literal["setup", "planning", "work", "review", "retro", "teardown"]
    agent: str | None = None  # None for framework events


# ---------------------------------------------------------------------------
# Framework Events
# ---------------------------------------------------------------------------

class ExperimentStartEvent(BaseEvent):
    """Emitted when the experiment begins."""

    event_type: Literal["experiment_start"] = "experiment_start"
    config_snapshot: dict  # Full ExperimentConfig as dict


class ExperimentEndEvent(BaseEvent):
    """Emitted when the experiment ends (any reason)."""

    event_type: Literal["experiment_end"] = "experiment_end"
    reason: Literal["completed", "budget_exhausted", "error", "manual_stop"]
    total_sprints_completed: int


class SprintStartEvent(BaseEvent):
    """Emitted at the beginning of each sprint."""

    event_type: Literal["sprint_start"] = "sprint_start"
    sprint_number: int


class SprintEndEvent(BaseEvent):
    """Emitted at the end of each sprint."""

    event_type: Literal["sprint_end"] = "sprint_end"
    sprint_number: int
    checkpoint_saved: bool


class PhaseStartEvent(BaseEvent):
    """Emitted when a phase begins within a sprint."""

    event_type: Literal["phase_start"] = "phase_start"


class PhaseEndEvent(BaseEvent):
    """Emitted when a phase ends within a sprint."""

    event_type: Literal["phase_end"] = "phase_end"


# ---------------------------------------------------------------------------
# Git Events
# ---------------------------------------------------------------------------

class CommitEvent(BaseEvent):
    """Emitted when an agent creates a git commit."""

    event_type: Literal["commit"] = "commit"
    sha: str
    message: str
    files: list[str]
    branch: str


class FileReadEvent(BaseEvent):
    """Emitted when an agent reads a file."""

    event_type: Literal["file_read"] = "file_read"
    path: str
    size_bytes: int


class FileWriteEvent(BaseEvent):
    """Emitted when an agent writes a file."""

    event_type: Literal["file_write"] = "file_write"
    path: str
    size_bytes: int
    is_new: bool


# ---------------------------------------------------------------------------
# PR Events
# ---------------------------------------------------------------------------

class PROpenEvent(BaseEvent):
    """Emitted when an agent opens a pull request."""

    event_type: Literal["pr_open"] = "pr_open"
    pr_id: str
    title: str
    branch: str
    files_changed: list[str]


class PRReviewEvent(BaseEvent):
    """Emitted when an agent reviews a pull request."""

    event_type: Literal["pr_review"] = "pr_review"
    pr_id: str
    verdict: Literal["approve", "reject", "comment"]
    comments: list[str]


class PRCommentEvent(BaseEvent):
    """Emitted when an agent comments on a pull request."""

    event_type: Literal["pr_comment"] = "pr_comment"
    pr_id: str
    comment: str


class PRMergeEvent(BaseEvent):
    """Emitted when a pull request is merged."""

    event_type: Literal["pr_merge"] = "pr_merge"
    pr_id: str
    merge_sha: str


# ---------------------------------------------------------------------------
# Communication Events
# ---------------------------------------------------------------------------

class MessageEvent(BaseEvent):
    """Emitted when an agent sends a direct message."""

    event_type: Literal["message"] = "message"
    to: str  # Recipient agent name
    content: str


class MeetingStatementEvent(BaseEvent):
    """Emitted when an agent speaks during a meeting."""

    event_type: Literal["meeting_statement"] = "meeting_statement"
    content: str
    meeting_type: Literal["planning", "retro"]


# ---------------------------------------------------------------------------
# Task Events
# ---------------------------------------------------------------------------

class TaskClaimEvent(BaseEvent):
    """Emitted when an agent claims a backlog task."""

    event_type: Literal["task_claim"] = "task_claim"
    task_id: str
    task_title: str


class TaskCompleteEvent(BaseEvent):
    """Emitted when an agent completes a backlog task."""

    event_type: Literal["task_complete"] = "task_complete"
    task_id: str


# ---------------------------------------------------------------------------
# Agent Memory Events
# ---------------------------------------------------------------------------

class ScratchpadUpdateEvent(BaseEvent):
    """Emitted when an agent updates their scratchpad."""

    event_type: Literal["scratchpad_update"] = "scratchpad_update"
    sections_updated: list[str]
    new_line_count: int


# ---------------------------------------------------------------------------
# Access Control Events
# ---------------------------------------------------------------------------

class AccessRequestEvent(BaseEvent):
    """Emitted when an agent requests access to a tool."""

    event_type: Literal["access_request"] = "access_request"
    tool_name: str
    granted: bool
    reason: str | None = None


class TierViolationEvent(BaseEvent):
    """Emitted when an agent attempts to use a tool above their tier."""

    event_type: Literal["tier_violation"] = "tier_violation"
    tool_name: str
    tier_required: str


# ---------------------------------------------------------------------------
# Tool Usage Events
# ---------------------------------------------------------------------------

class ToolCallEvent(BaseEvent):
    """Emitted when an agent calls a tool."""

    event_type: Literal["tool_call"] = "tool_call"
    tool_name: str
    args_summary: str  # Truncated args for log readability
    result_summary: str  # Truncated result
    duration_ms: int


# ---------------------------------------------------------------------------
# Discriminated Union
# ---------------------------------------------------------------------------

Event = Annotated[
    Union[
        ExperimentStartEvent,
        ExperimentEndEvent,
        SprintStartEvent,
        SprintEndEvent,
        PhaseStartEvent,
        PhaseEndEvent,
        CommitEvent,
        FileReadEvent,
        FileWriteEvent,
        PROpenEvent,
        PRReviewEvent,
        PRCommentEvent,
        PRMergeEvent,
        MessageEvent,
        MeetingStatementEvent,
        TaskClaimEvent,
        TaskCompleteEvent,
        ScratchpadUpdateEvent,
        AccessRequestEvent,
        TierViolationEvent,
        ToolCallEvent,
    ],
    Field(discriminator="event_type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
