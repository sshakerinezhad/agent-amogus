# Data Model: AMOGUS Core Framework v1

**Phase 1 Output** — All Pydantic models, relationships, validation rules, and state transitions.

## Model Architecture

```
models/
├── config.py    → ExperimentConfig, AgentConfig, TokenBudgetConfig, PacingConfig, ScenarioConfig
├── events.py    → BaseEvent + 21 event types (discriminated union)
└── mission.py   → MissionProfile, DefenseRegime, BacklogConfig, BacklogPhase

providers/
└── base.py      → Message, ToolCall, ToolResult, ToolDefinition, Response, TokenUsage
```

All models are Pydantic v2 `BaseModel` subclasses with full type hints and validators.

---

## 1. Configuration Models (`models/config.py`)

### ExperimentConfig

The top-level validated configuration for a complete experiment run. Composed from multiple YAML files by the scenario loader.

```python
class ExperimentConfig(BaseModel):
    """Complete experiment configuration — frozen after validation."""
    model_config = ConfigDict(frozen=True)

    run_id: str                          # "amogus-2026-03-04-001"
    target_repo: str                     # URL or local path to clone
    repo_commit: str | None = None       # Pin to specific commit (None = HEAD)
    team: list[AgentConfig]              # 2-6 agents
    mission_assignments: dict[str, str]  # agent_name → mission_file_path
    defense_regime: DefenseRegime
    backlog: BacklogConfig                   # Project backlog for the experiment
    num_sprints: int = Field(default=5, ge=1, le=50)
    seed: int = Field(default=42)
    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    pacing: PacingConfig = Field(default_factory=PacingConfig)
    evaluator_model: str = "claude-haiku-4-5"  # Cheaper model for evaluation
    run_dir: Path | None = None          # Set at runtime, not from YAML

    @field_validator("team")
    @classmethod
    def validate_team_size(cls, v: list) -> list:
        if len(v) < 2:
            raise ValueError("Experiment requires at least 2 agents")
        if len(v) > 6:
            raise ValueError("Experiment supports at most 6 agents")
        names = [a.name for a in v]
        if len(names) != len(set(names)):
            raise ValueError("Agent names must be unique")
        return v

    @field_validator("mission_assignments")
    @classmethod
    def validate_missions_reference_team(cls, v: dict, info) -> dict:
        if "team" in info.data:
            team_names = {a.name for a in info.data["team"]}
            for agent_name in v:
                if agent_name not in team_names:
                    raise ValueError(f"Mission assigned to unknown agent: {agent_name}")
        return v
```

### AgentConfig

```python
class AgentConfig(BaseModel):
    """Agent profile loaded from YAML."""
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9-]*$")
    role: str                            # "Senior Backend Developer"
    model: str                           # "claude-opus-4-6", "gpt-4o"
    tool_access: list[str] = ["standard"]  # ["standard"] or ["standard", "sensitive"]
    system_prompt: str
    specialties: list[str] = []          # ["backend", "security", "databases"]
```

### TokenBudgetConfig

```python
class TokenBudgetConfig(BaseModel):
    """Token budget limits for cost control."""
    per_agent_per_sprint: int = Field(default=100_000, ge=1000)
    per_experiment: int = Field(default=2_000_000, ge=10_000)
```

### PacingConfig

```python
class PacingConfig(BaseModel):
    """Bounded work per sprint to prevent any agent from dominating."""
    max_tool_calls_per_turn: int = Field(default=50, ge=5)
    max_turns_per_phase: int = Field(default=20, ge=1)
    planning_rounds: int = Field(default=2, ge=1, le=5)
    retro_rounds: int = Field(default=1, ge=1, le=3)
```

### ScenarioConfig

```python
class ScenarioConfig(BaseModel):
    """Raw scenario YAML — validated, then composed into ExperimentConfig by scenario.py."""
    target_repo: str
    repo_commit: str | None = None
    team: list[dict[str, str]]               # [{profile: "...", mission: "..."}]
    defense_regime: str                       # Path to defense YAML
    backlog: str                              # Path to backlog YAML
    num_sprints: int = Field(default=5, ge=1, le=50)
    seed: int = Field(default=42)
    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    pacing: PacingConfig = Field(default_factory=PacingConfig)
    evaluator_model: str = "claude-haiku-4-5"
```

---

## 2. Mission Models (`models/mission.py`)

### MissionProfile

```python
class MissionProfile(BaseModel):
    """Covert mission definition loaded from YAML."""
    model_config = ConfigDict(frozen=True)

    codename: str                        # "PHANTOM GATE"
    category: str                        # "supply-chain", "data-exfil", "logic-bomb"
    objective: str                       # Human-readable objective
    milestones: list[str] = Field(min_length=2, max_length=6)
    briefing: str                        # Injected into adversarial agent's system prompt
```

### DefenseRegime

```python
class DefenseRegime(BaseModel):
    """Defense/detection configuration for the experiment."""
    model_config = ConfigDict(frozen=True)

    name: str                            # "code-review", "full-paranoia"
    description: str
    components: list[str] = []           # ["code_review", "static_analysis", "watchdog"]
    agent_briefing: str | None = None    # Extra system prompt for briefed teams
    watchdog_agent: str | None = None    # Agent name designated as security watchdog
```

### BacklogConfig

```python
class BacklogConfig(BaseModel):
    """Project backlog loaded from YAML."""
    project: str
    repo: str
    phases: list[BacklogPhase]

class BacklogPhase(BaseModel):
    name: str
    priority: int = Field(ge=1)
    tasks: list[str]
    ongoing: bool = False
```

---

## 3. Event Models (`models/events.py`)

### BaseEvent

All events inherit from this. The `event_type` field is the discriminator.

```python
class BaseEvent(BaseModel):
    """Base class for all events in the append-only log."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sprint: int = Field(ge=0)
    phase: Literal["setup", "planning", "work", "review", "retro", "teardown"]
    agent: str | None = None             # None for framework events
```

### Event Type Catalog

#### Framework Events

```python
class ExperimentStartEvent(BaseEvent):
    event_type: Literal["experiment_start"] = "experiment_start"
    config_snapshot: dict                # Full ExperimentConfig as dict

class ExperimentEndEvent(BaseEvent):
    event_type: Literal["experiment_end"] = "experiment_end"
    reason: Literal["completed", "budget_exhausted", "error", "manual_stop"]
    total_sprints_completed: int

class SprintStartEvent(BaseEvent):
    event_type: Literal["sprint_start"] = "sprint_start"
    sprint_number: int

class SprintEndEvent(BaseEvent):
    event_type: Literal["sprint_end"] = "sprint_end"
    sprint_number: int
    checkpoint_saved: bool

class PhaseStartEvent(BaseEvent):
    event_type: Literal["phase_start"] = "phase_start"

class PhaseEndEvent(BaseEvent):
    event_type: Literal["phase_end"] = "phase_end"
```

#### Git Events

```python
class CommitEvent(BaseEvent):
    event_type: Literal["commit"] = "commit"
    sha: str
    message: str
    files: list[str]
    branch: str

class FileReadEvent(BaseEvent):
    event_type: Literal["file_read"] = "file_read"
    path: str
    size_bytes: int

class FileWriteEvent(BaseEvent):
    event_type: Literal["file_write"] = "file_write"
    path: str
    size_bytes: int
    is_new: bool
```

#### PR Events

```python
class PROpenEvent(BaseEvent):
    event_type: Literal["pr_open"] = "pr_open"
    pr_id: str
    title: str
    branch: str
    files_changed: list[str]

class PRReviewEvent(BaseEvent):
    event_type: Literal["pr_review"] = "pr_review"
    pr_id: str
    verdict: Literal["approve", "reject", "comment"]
    comments: list[str]

class PRCommentEvent(BaseEvent):
    event_type: Literal["pr_comment"] = "pr_comment"
    pr_id: str
    comment: str

class PRMergeEvent(BaseEvent):
    event_type: Literal["pr_merge"] = "pr_merge"
    pr_id: str
    merge_sha: str
```

#### Communication Events

```python
class MessageEvent(BaseEvent):
    event_type: Literal["message"] = "message"
    to: str                              # Recipient agent name
    content: str

class MeetingStatementEvent(BaseEvent):
    event_type: Literal["meeting_statement"] = "meeting_statement"
    content: str
    meeting_type: Literal["planning", "retro"]
```

#### Task Events

```python
class TaskClaimEvent(BaseEvent):
    event_type: Literal["task_claim"] = "task_claim"
    task_id: str
    task_title: str

class TaskCompleteEvent(BaseEvent):
    event_type: Literal["task_complete"] = "task_complete"
    task_id: str
```

#### Agent Memory Events

```python
class ScratchpadUpdateEvent(BaseEvent):
    event_type: Literal["scratchpad_update"] = "scratchpad_update"
    sections_updated: list[str]
    new_line_count: int
```

#### Access Control Events

```python
class AccessRequestEvent(BaseEvent):
    event_type: Literal["access_request"] = "access_request"
    tool_name: str
    granted: bool
    reason: str | None = None

class TierViolationEvent(BaseEvent):
    event_type: Literal["tier_violation"] = "tier_violation"
    tool_name: str
    tier_required: str
```

#### Tool Usage Events

```python
class ToolCallEvent(BaseEvent):
    event_type: Literal["tool_call"] = "tool_call"
    tool_name: str
    args_summary: str                    # Truncated args for log readability
    result_summary: str                  # Truncated result
    duration_ms: int
```

### Discriminated Union

```python
Event = Annotated[
    Union[
        ExperimentStartEvent, ExperimentEndEvent,
        SprintStartEvent, SprintEndEvent,
        PhaseStartEvent, PhaseEndEvent,
        CommitEvent, FileReadEvent, FileWriteEvent,
        PROpenEvent, PRReviewEvent, PRCommentEvent, PRMergeEvent,
        MessageEvent, MeetingStatementEvent,
        TaskClaimEvent, TaskCompleteEvent,
        ScratchpadUpdateEvent,
        AccessRequestEvent, TierViolationEvent,
        ToolCallEvent,
    ],
    Field(discriminator="event_type")
]

# TypeAdapter for JSONL serialization/deserialization
EventAdapter = TypeAdapter(Event)
```

---

## 4. Provider Models (`providers/base.py`)

These are the canonical types that cross the provider boundary. All providers normalize to/from these types.

### Message

```python
class Message(BaseModel):
    """Normalized conversation message."""
    role: Literal["user", "assistant", "tool_result"]
    content: str | None = None
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []
```

### ToolCall

```python
class ToolCall(BaseModel):
    """A tool call issued by the model — arguments always a parsed dict."""
    id: str
    name: str
    arguments: dict[str, Any]
```

### ToolResult

```python
class ToolResult(BaseModel):
    """Result of executing a tool call."""
    tool_call_id: str
    content: str
    is_error: bool = False
```

### ToolDefinition

```python
class ToolDefinition(BaseModel):
    """Tool schema in canonical form."""
    name: str
    description: str
    parameters: dict[str, Any]          # JSON Schema object
    tier: Literal["standard", "sensitive"] = "standard"
```

### Response

```python
class Response(BaseModel):
    """Normalized response from any provider."""
    content: str | None = None
    tool_calls: list[ToolCall] = []
    stop_reason: Literal["end_turn", "tool_calls", "max_tokens"]
    usage: TokenUsage
```

### TokenUsage

```python
class TokenUsage(BaseModel):
    """Normalized token counts."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __iadd__(self, other: "TokenUsage") -> "TokenUsage":
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        return self
```

---

## 5. Runtime Models (not persisted, used in-memory)

### SprintTask

```python
class SprintTask(BaseModel):
    """A task within a sprint — agent-decomposed during planning."""
    id: str                              # "S3-1"
    title: str
    assigned_to: str | None = None
    blocked_by: list[str] = []
    status: Literal["pending", "in_progress", "done"] = "pending"
    acceptance: str = ""
```

### PullRequest

```python
class PullRequest(BaseModel):
    """Local PR tracker — no GitHub API needed."""
    id: str                              # "PR-001"
    title: str
    author: str
    source_branch: str
    target_branch: str = "main"
    files_changed: list[str] = []
    status: Literal["open", "merged", "closed"] = "open"
    reviews: list[PRReview] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PRReview(BaseModel):
    reviewer: str
    verdict: Literal["approve", "reject", "comment"]
    comments: list[str] = []
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Checkpoint

```python
class Checkpoint(BaseModel):
    """Sprint-level checkpoint for resume."""
    run_id: str
    completed_sprint: int
    scratchpads: dict[str, str]          # agent_name → content
    backlog_state: dict[str, Any]        # serialized BacklogConfig
    sprint_tasks: dict[int, list[dict]]  # sprint_number → serialized tasks
    git_branches: dict[str, str]         # branch_name → commit SHA
    token_usage: dict[str, dict]         # agent_name → TokenUsage as dict
    pr_state: list[dict]                 # serialized PullRequests
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 6. Entity Relationships

```
ExperimentConfig
├── has many → AgentConfig (team)
├── has many → MissionProfile (via mission_assignments)
├── has one  → DefenseRegime
├── has one  → TokenBudgetConfig
├── has one  → PacingConfig
└── has one  → BacklogConfig (backlog)

Agent (runtime)
├── has one  → AgentConfig
├── has one  → Provider (via provider factory)
├── has one  → Scratchpad (markdown content)
├── has one  → TokenUsage (accumulated)
├── has zero or one → MissionProfile (adversarial only)
└── produces → Event (via tool calls)

Sprint (runtime)
├── has many → SprintTask
├── has many → PullRequest
└── produces → Event (start, end, phase transitions)

EventLog
├── contains → Event (append-only JSONL)
└── derives  → SQLite index (post-run)

Checkpoint
├── captures → Sprint state
├── captures → Scratchpad state
├── captures → Git branch state
├── captures → Token usage state
└── captures → PR state
```

---

## 7. State Transitions

### Sprint Lifecycle

```
setup → [sprint 1..N] → teardown

Each sprint:
  planning → work → review → retro
```

### SprintTask Status

```
pending → in_progress → done
```

### PullRequest Status

```
open → merged   (approved and merged)
open → closed   (rejected or abandoned)
```

### Agent Turn Flow

```
receive_prompt → call_provider → [tool_calls → execute_tools → call_provider]* → end_turn
                                 ↑ budget check after each provider call ↑
```

---

## 8. Validation Rules Summary

| Model | Rule | Enforcement |
|---|---|---|
| ExperimentConfig | 2-6 agents, unique names | `field_validator` |
| ExperimentConfig | Mission targets must reference team members | `field_validator` |
| AgentConfig | Name: lowercase alphanumeric + hyphens | `Field(pattern=...)` |
| TokenBudgetConfig | Minimums: 1000/agent/sprint, 10000/experiment | `Field(ge=...)` |
| PacingConfig | Sensible ranges for all limits | `Field(ge=..., le=...)` |
| MissionProfile | 2-6 milestones | `Field(min_length=..., max_length=...)` |
| BaseEvent | Phase is a known literal | `Literal[...]` |
| Event (union) | Discriminated on `event_type` | `Field(discriminator=...)` |
| SprintTask | Status transitions enforced | Orchestrator logic |
| PullRequest | Status transitions enforced | PR tracker logic |
