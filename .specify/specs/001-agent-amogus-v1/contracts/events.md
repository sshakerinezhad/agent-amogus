# Contract: Event System

**Module**: `amogus/event_log.py` + `amogus/models/events.py`

The event log is the single source of truth. It is append-only, never mutated. All views (scores, dashboard, reports) derive from it.

## EventLog Interface

```python
class EventLog:
    """
    Append-only JSONL event writer and reader.

    Thread-safe: uses a file lock for concurrent appends.
    Async: write operations are dispatched to a thread pool.
    """

    def __init__(self, path: Path):
        """
        Initialize the event log.

        Args:
            path: Path to the .jsonl file. Created if it doesn't exist.

        Raises:
            AmogusError: If the path exists and is not a valid JSONL file.
        """
        ...

    async def append(self, event: BaseEvent) -> None:
        """
        Append a single event to the log.

        The event is serialized to JSON and written as one line.
        A newline is always appended.
        The file is flushed after each write (durability).

        Args:
            event: Any event model instance.
        """
        ...

    async def read_all(self) -> list[Event]:
        """
        Read all events from the log.

        Returns:
            List of deserialized Event objects (discriminated union).
            Events are in chronological order (append order).
        """
        ...

    async def read_filtered(
        self,
        event_type: str | None = None,
        sprint: int | None = None,
        agent: str | None = None,
        phase: str | None = None,
    ) -> list[Event]:
        """
        Read events matching filter criteria.

        For v1, this scans the full file and filters in memory.
        For analysis, use the SQLite index instead.
        """
        ...

    async def tail(self, n: int = 10) -> list[Event]:
        """Read the last N events."""
        ...

    @property
    def path(self) -> Path:
        """The path to the JSONL file."""
        ...
```

## SQLite Index Builder

```python
async def build_sqlite_index(jsonl_path: Path, sqlite_path: Path) -> None:
    """
    Build a SQLite index from a JSONL event log.

    This is a post-run operation. The SQLite file is a derived artifact
    that can be deleted and regenerated at any time.

    Schema:
        events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            sprint INTEGER NOT NULL,
            phase TEXT NOT NULL,
            agent TEXT,
            data JSON NOT NULL
        )

    Indexes:
        idx_events_type (event_type)
        idx_events_sprint (sprint)
        idx_events_agent (agent)
        idx_events_phase (phase)

    Args:
        jsonl_path: Path to the source JSONL file.
        sqlite_path: Path for the output SQLite file.
    """
    ...
```

## JSONL Format

Each line is a complete JSON object representing one event:

```jsonl
{"event_id":"550e8400-e29b-41d4-a716-446655440000","event_type":"experiment_start","timestamp":"2026-03-04T10:00:00Z","sprint":0,"phase":"setup","agent":null,"config_snapshot":{...}}
{"event_id":"550e8400-e29b-41d4-a716-446655440001","event_type":"sprint_start","timestamp":"2026-03-04T10:00:01Z","sprint":1,"phase":"planning","agent":null,"sprint_number":1}
{"event_id":"550e8400-e29b-41d4-a716-446655440002","event_type":"meeting_statement","timestamp":"2026-03-04T10:00:05Z","sprint":1,"phase":"planning","agent":"agent-alpha","content":"I'll take the auth module refactoring.","meeting_type":"planning"}
```

## Invariants

1. **Append-only**: No method exists to update or delete events.
2. **Ordered**: Events are in chronological append order. Timestamps are monotonically non-decreasing.
3. **Complete**: Every tool call, every agent response, every phase transition produces at least one event.
4. **Self-contained**: Each JSON line deserializes independently. No cross-line references needed.
5. **Durable**: Each append flushes to disk. A crash mid-experiment loses at most the current event.

## Event Type Registry

| event_type | Model | Agent? | Description |
|---|---|---|---|
| `experiment_start` | ExperimentStartEvent | No | Experiment begins, config snapshot |
| `experiment_end` | ExperimentEndEvent | No | Experiment ends (completed/error/budget) |
| `sprint_start` | SprintStartEvent | No | Sprint begins |
| `sprint_end` | SprintEndEvent | No | Sprint ends, checkpoint saved |
| `phase_start` | PhaseStartEvent | No | Phase transition |
| `phase_end` | PhaseEndEvent | No | Phase complete |
| `commit` | CommitEvent | Yes | Agent creates a git commit |
| `file_read` | FileReadEvent | Yes | Agent reads a file |
| `file_write` | FileWriteEvent | Yes | Agent writes a file |
| `pr_open` | PROpenEvent | Yes | Agent opens a pull request |
| `pr_review` | PRReviewEvent | Yes | Agent reviews a PR |
| `pr_comment` | PRCommentEvent | Yes | Agent comments on a PR |
| `pr_merge` | PRMergeEvent | No | Framework merges an approved PR |
| `message` | MessageEvent | Yes | Agent sends a message |
| `meeting_statement` | MeetingStatementEvent | Yes | Agent speaks in a meeting |
| `task_claim` | TaskClaimEvent | Yes | Agent claims a task |
| `task_complete` | TaskCompleteEvent | Yes | Agent marks task done |
| `scratchpad_update` | ScratchpadUpdateEvent | Yes | Agent updates scratchpad |
| `access_request` | AccessRequestEvent | Yes | Agent requests elevated access |
| `tier_violation` | TierViolationEvent | Yes | Agent attempted restricted tool |
| `tool_call` | ToolCallEvent | Yes | General tool invocation record |
