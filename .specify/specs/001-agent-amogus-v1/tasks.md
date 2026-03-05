# Tasks: AMOGUS Core Framework v1

**Input**: Design documents from `/specs/001-agent-amogus-v1/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not included as individual tasks — the spec does not explicitly request TDD. Test infrastructure is set up in Phase 1. Test writing can be done per-module during or after implementation.

**Organization**: Tasks are grouped by user story derived from spec scenarios:
- **US1** → Scenario 1: Running a Basic Experiment (P1 — MVP)
- **US2** → Scenario 2: Resume & Ablation Study (P2)
- **US3** → Scenario 4: Live Dashboard Observation (P2)
- **US4** → Scenario 5: Post-Run Analysis & Reporting (P2)
- **US5** → Scenario 3: Example Configs & Documentation (P3)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Include exact file paths in descriptions

## Path Conventions

- **Source package**: `amogus/` at repository root
- **Sub-packages**: `amogus/models/`, `amogus/providers/`
- **Tests**: `tests/`, `tests/test_models/`, `tests/test_providers/`
- **YAML configs**: `agents/`, `missions/`, `defenses/`, `backlogs/`, `scenarios/`
- **Runtime artifacts**: `runs/<run-id>/` (generated, not committed)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, package structure, dependency declaration, test infrastructure

- [x] T001 Create project directory structure: `amogus/`, `amogus/models/`, `amogus/providers/`, `agents/blue/`, `agents/red/`, `missions/`, `defenses/`, `backlogs/`, `scenarios/`, `tests/`, `tests/test_models/`, `tests/test_providers/`
- [x] T002 Create `pyproject.toml` with project metadata, Python 3.11+ requirement, dependencies (pydantic>=2.0, typer>=0.9, gitpython>=3.1, rich>=13.0, pyyaml>=6.0, anthropic>=0.25, openai>=1.0), dev dependencies (pytest, pytest-asyncio, ruff, pyright), CLI entry point `amogus = "amogus.cli:app"`, ruff and pyright configuration sections
- [x] T003 [P] Create `amogus/__init__.py` with `__version__ = "0.1.0"`
- [x] T004 [P] Create `tests/conftest.py` with shared fixtures: MockProvider (implements Provider ABC with canned responses), temp_repo (GitPython test repo in tmpdir), temp_run_dir (with scratchpads/ and worktrees/ subdirs), sample ExperimentConfig/AgentConfig factories

**Checkpoint**: Project installable via `pip install -e ".[dev]"`, pytest runs with no tests collected

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and provider abstraction that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Create `amogus/exceptions.py` — Define AmogusError (base), ConfigError (invalid configs), SandboxViolation (path escape), BudgetExhaustedError (token limit), MaxIterationsError (agentic loop limit), ProviderError (API failures after retries)
- [x] T006 [P] Create `amogus/models/__init__.py` — Re-export all public model classes from config, events, and mission submodules for convenient `from amogus.models import ExperimentConfig` usage
- [x] T007 [P] Create `amogus/models/config.py` — ExperimentConfig (frozen, run_id, target_repo, team list with 2-6 unique name validation + upper bound enforcement, mission_assignments with team reference validation, defense_regime, backlog: BacklogConfig, num_sprints 1-50 default 5, seed default 42, token_budget, pacing, evaluator_model, run_dir), AgentConfig (frozen, name with lowercase pattern, role, model, tool_access default ["standard"], system_prompt, specialties), TokenBudgetConfig (per_agent_per_sprint default 100K min 1K, per_experiment default 2M min 10K), PacingConfig (max_tool_calls_per_turn default 50, max_turns_per_phase default 20, planning_rounds default 2, retro_rounds default 1), ScenarioConfig (raw scenario YAML validation: target_repo, repo_commit optional, team as list of dicts, defense_regime path, backlog path, num_sprints, seed, token_budget, pacing, evaluator_model — composed into ExperimentConfig by scenario.py)
- [x] T008 [P] Create `amogus/models/mission.py` — MissionProfile (frozen, codename, category, objective, milestones 2-6 items, briefing), DefenseRegime (frozen, name, description, components list, agent_briefing optional, watchdog_agent optional), BacklogConfig (project, repo, phases list), BacklogPhase (name, priority ge 1, tasks list, ongoing default False)
- [x] T009 [P] Create `amogus/models/events.py` — BaseEvent (event_id uuid4 default, event_type str, timestamp utc default, sprint ge 0, phase Literal setup/planning/work/review/retro/teardown, agent optional), all 21 event types per data-model.md (ExperimentStartEvent, ExperimentEndEvent, SprintStartEvent, SprintEndEvent, PhaseStartEvent, PhaseEndEvent, CommitEvent, FileReadEvent, FileWriteEvent, PROpenEvent, PRReviewEvent, PRCommentEvent, PRMergeEvent, MessageEvent, MeetingStatementEvent, TaskClaimEvent, TaskCompleteEvent, ScratchpadUpdateEvent, AccessRequestEvent, TierViolationEvent, ToolCallEvent), Event discriminated union on event_type field, EventAdapter TypeAdapter
- [x] T010 [P] Create `amogus/providers/base.py` — Provider ABC with abstract methods: async complete(system, messages, tools, max_tokens) -> Response, format_tool_results(response, results) -> list[Message], property model_name -> str. Canonical types: Message (role literal, content optional, tool_calls list, tool_results list), ToolCall (id, name, arguments dict), ToolResult (tool_call_id, content, is_error), ToolDefinition (name, description, parameters JSON Schema dict, tier), Response (content optional, tool_calls, stop_reason literal end_turn/tool_calls/max_tokens, usage), TokenUsage (input_tokens, output_tokens, cache_read/write_tokens, total property, __iadd__)
- [x] T011 Create `amogus/providers/__init__.py` — _PROVIDERS registry dict mapping model prefix to Provider subclass, register_provider(prefix, cls), create_provider(model, **kwargs) factory that matches model prefix to registered provider and raises ConfigError for unknown models or missing API key env vars

**Checkpoint**: `from amogus.models import ExperimentConfig, Event` works. `from amogus.providers import create_provider` works. All Pydantic models validate correctly.

---

## Phase 3: User Story 1 — Run a Basic Experiment (Priority: P1) MVP

**Goal**: A researcher can configure and run a complete multi-sprint adversarial experiment on a target repository, producing an event log with every agent action recorded.

**Independent Test**: `amogus run --scenario scenarios/example-basic.yaml` completes all configured sprints. `runs/<run-id>/events.jsonl` contains structured events covering all phases and agent actions. Agents produce commits, PRs, and messages.

### Implementation for User Story 1

- [x] T012 [P] [US1] Create `amogus/event_log.py` — EventLog class: __init__(path: Path) creating file if needed, async append(event: BaseEvent) serializing to JSON line with flush, async read_all() -> list[Event] parsing via EventAdapter, async read_filtered(event_type/sprint/agent/phase) scanning and filtering in memory, async tail(n) reading last N events, thread-safe via threading.Lock for concurrent appends, all file I/O via asyncio.to_thread()
- [x] T013 [P] [US1] Create `amogus/sandbox.py` — validate_path(agent_name, path, workspace) resolving to absolute path, enforcing path is within workspace (no ../ escape), blocking access to paths matching `*/scratchpads/*` for other agent names, blocking direct .git directory access, raising SandboxViolation with descriptive message on any violation
- [x] T014 [P] [US1] Create `amogus/memory.py` — load_scratchpad(path: Path) -> str reading markdown file, update_scratchpad(path: Path, sections: dict[str, str]) merging section updates into existing content, compress_scratchpad(content: str, max_lines: int = 500) -> str taking first line of oldest sprint entries keeping last 3 uncompressed per R6, build_initial_scratchpad(agent_config: AgentConfig) -> str creating template with role/sprint history/current sprint/observations/questions sections
- [x] T015 [P] [US1] Create `amogus/backlog.py` — BacklogManager class: __init__(config: BacklogConfig), get_available_tasks() listing unclaimed tasks by priority, claim_task(agent_name, task_id) marking as in_progress with TaskClaimEvent, complete_task(task_id) marking as done, get_sprint_tasks(sprint: int) returning current sprint task assignments, to_context_string() formatting backlog for agent prompt injection, SprintTask runtime model (id, title, assigned_to, status pending/in_progress/done)
- [x] T016 [P] [US1] Create `amogus/pull_request.py` — PullRequestTracker class: __init__(), open_pr(author, title, branch, files) -> PullRequest creating PR with auto-incrementing ID, review_pr(pr_id, reviewer, verdict, comments) adding review, merge_pr(pr_id, repo: Repo) merging branch into main via GitPython (wrapped in asyncio.to_thread), list_open_prs() -> list[PullRequest], get_pr(pr_id) -> PullRequest, using PullRequest and PRReview models from data-model.md
- [x] T017 [P] [US1] Create `amogus/providers/anthropic.py` — AnthropicProvider(Provider): __init__(model, api_key from ANTHROPIC_API_KEY env), complete() using anthropic.AsyncAnthropic client with system= param, tool schema translation (parameters -> input_schema), response normalization (block.input for tool args, stop_reason mapping end_turn/tool_use/max_tokens), format_tool_results() creating user message with tool_result content blocks, token usage extraction (input_tokens, output_tokens, cache_read/write), exponential backoff retry on 429/500/502/503/529 up to max_retries=5
- [x] T018 [P] [US1] Create `amogus/providers/openai.py` — OpenAIProvider(Provider): __init__(model, api_key from OPENAI_API_KEY env), complete() using openai.AsyncOpenAI client prepending system message, tool schema wrapping in {"type":"function","function":{...}} format, response normalization (json.loads on tool_call.function.arguments, finish_reason mapping stop/tool_calls/length), format_tool_results() creating separate tool-role messages per result, token usage extraction (prompt_tokens -> input_tokens), exponential backoff retry on 429/500/502/503 up to max_retries=5
- [x] T019 [US1] Create `amogus/tools.py` — ToolInfo dataclass (name, tier, description, parameters JSON Schema, handler), ToolContext dataclass (workspace Path, scratchpad_dir Path, run_dir Path, agent_name, sprint, phase, pr_tracker, backlog), _TOOL_REGISTRY dict, @tool(name, tier, description, parameters) decorator registering handler, async dispatch_tool(agent_name, tool_name, arguments, allowed_tiers, event_log, context) -> str with tier enforcement logging TierViolationEvent on deny, get_tool_definitions(tiers) -> list[ToolDefinition] for provider schemas. Implement all 15 standard tools delegating to domain modules: file_read/file_write/file_list -> sandbox.validate_path + file I/O, git_commit/git_diff/git_log -> asyncio.to_thread(GitPython), open_pr/review_pr/comment_pr -> pull_request tracker, send_message -> event_log append MessageEvent, claim_task/complete_task -> backlog manager, update_scratchpad -> memory module, run_tests/run_linter -> subprocess with whitelisted commands. Implement 5 sensitive tools: access_secrets, modify_ci_cd, deploy, db_admin, modify_access_control
- [x] T020 [US1] Create `amogus/agent.py` — Agent class: __init__(config: AgentConfig, provider: Provider, event_log: EventLog, scratchpad_path: Path, workspace: Path, mission: MissionProfile | None, budget: int), build_context(sprint, phase, backlog_context, meeting_transcript) -> list[Message] injecting system prompt + scratchpad + sprint context + mission briefing for red agents, async execute_turn(prompt) -> str running agentic tool-use loop (send to provider, if tool_calls execute via dispatch_tool and append results, loop until end_turn or max iterations), token_usage accumulation via += on each provider response, budget check after each call raising BudgetExhaustedError, async safe_agent_turn() wrapper catching all exceptions returning AgentResult(agent, output|error), async speak(context) for meeting phases (single provider call, no tool use)
- [x] T021 [US1] Create `amogus/orchestrator.py` — Orchestrator class: __init__(config: ExperimentConfig, agents: list[Agent], event_log: EventLog, backlog: BacklogManager, pr_tracker: PullRequestTracker), async run() driving full experiment (setup_workspace -> emit ExperimentStartEvent -> sprint loop -> emit ExperimentEndEvent), async setup_workspace() cloning target repo + creating per-agent worktrees via GitPython (repo.git.worktree("add",...)), async sprint(n) executing 4 phases with events, async planning_phase() sequential round-robin meeting (2 rounds per PacingConfig), async work_phase() parallel via asyncio.TaskGroup calling safe_agent_turn per agent, async review_phase() collecting open PRs and assigning reviewers sequentially, merging approved PRs, async retro_phase() sequential round-robin meeting (1 round), budget tracking across agents, clean shutdown on BudgetExhaustedError
- [x] T022 [P] [US1] Create `amogus/scenario.py` — async load_scenario(path: Path) -> ExperimentConfig reading scenario YAML, validating against ScenarioConfig Pydantic model, resolving profile/mission/defense/backlog file paths relative to repo root, loading each referenced YAML file, parsing agent profiles into AgentConfig list, parsing mission assignments mapping agent names to loaded MissionProfile paths, parsing defense regime, loading backlog, composing all into ExperimentConfig with auto-generated run_id (amogus-{date}-{seq}), creating run_dir under runs/
- [x] T023 [US1] Create `amogus/cli.py` — Typer app with app = typer.Typer(), run command: @app.command() taking --scenario Path argument, loading scenario via load_scenario(), creating providers via create_provider() for each agent, constructing Agent instances, constructing Orchestrator, running asyncio event loop with orchestrator.run(), printing run summary on completion, error handling for ConfigError/ProviderError/BudgetExhaustedError with user-friendly messages

**Checkpoint**: `amogus run --scenario scenarios/example-basic.yaml` runs a complete experiment. Event log captures all phases. Agents interact via tools.

---

## Phase 4: User Story 2 — Resume & Ablation Study (Priority: P2)

**Goal**: A researcher can resume a crashed experiment from the last completed sprint, and can rerun experiments with single-variable changes for comparative analysis.

**Independent Test**: Start an experiment, kill it mid-run, then `amogus resume <run-id>` continues from the last checkpoint. Two runs with identical configs except one variable produce comparable event logs.

### Implementation for User Story 2

- [ ] T024 [P] [US2] Create `amogus/checkpoint.py` — Checkpoint Pydantic model (run_id, completed_sprint, scratchpads dict, backlog_state dict, sprint_tasks dict, git_branches dict mapping branch->SHA, token_usage dict, pr_state list, timestamp), async save_checkpoint(run_dir: Path, checkpoint: Checkpoint) writing to run_dir/checkpoint.json, async load_checkpoint(run_dir: Path) -> Checkpoint reading and validating, capture_state(orchestrator) -> Checkpoint extracting current state from orchestrator/agents/backlog/PR tracker
- [ ] T025 [US2] Integrate checkpoint save into orchestrator sprint loop — call save_checkpoint after each completed sprint in amogus/orchestrator.py, emit SprintEndEvent with checkpoint_saved=True, handle checkpoint save errors gracefully (log warning, don't crash experiment)
- [ ] T026 [US2] Add `resume` command to CLI in `amogus/cli.py` — @app.command() taking run_id argument, locating run_dir in runs/, loading checkpoint, loading original ExperimentConfig from events.jsonl ExperimentStartEvent config_snapshot, verifying git branch SHAs match checkpoint, reconstructing agents with scratchpad/token state, continuing orchestrator.run() from completed_sprint + 1
- [ ] T027 [US2] Add git state verification and agent state reconstruction helpers in `amogus/checkpoint.py` — verify_git_state(run_dir, checkpoint) comparing actual branch HEAs to checkpoint, restore_agent_state(agent, checkpoint) loading scratchpad content and token counters, raise ConfigError if git state diverged

**Checkpoint**: Experiment survives process kill and resumes cleanly. Same config with different seed/defense produces different results.

---

## Phase 5: User Story 3 — Live Dashboard (Priority: P2)

**Goal**: An observer can watch a live experiment with agent activity, sprint progress, and a classified adversarial panel showing mission progress.

**Independent Test**: Run an experiment and verify the Rich TUI shows real-time updates for agent actions, sprint/phase transitions, and adversarial mission status in a separate panel.

### Implementation for User Story 3

- [ ] T028 [US3] Create `amogus/dashboard.py` — Rich Live dashboard using Layout with panels: AgentPanel (table showing each agent's current status/action/token usage), SprintPanel (current sprint N/M, current phase, progress bar), EventFeed (scrolling list of recent events with color-coded types), ClassifiedPanel (adversarial agent mission progress, milestone status, scratchpad excerpts — red-themed), update(event: BaseEvent) method to refresh panels from event stream, start()/stop() lifecycle methods using Rich Live context manager
- [ ] T029 [US3] Integrate dashboard with orchestrator in `amogus/orchestrator.py` — pass dashboard instance to orchestrator, call dashboard.update() on every event append, add --no-dashboard CLI flag to disable TUI for headless/CI runs, handle terminal resize gracefully

**Checkpoint**: `amogus run --scenario ...` shows a live-updating terminal dashboard during the experiment.

---

## Phase 6: User Story 4 — Post-Run Analysis & Reporting (Priority: P2)

**Goal**: After an experiment, the researcher gets a mission debrief with scores, timeline, strategy analysis, and adversarial journal excerpts, backed by a queryable SQLite index.

**Independent Test**: After a completed run, `amogus report <run-id>` produces `runs/<run-id>/report/debrief.md` and `debrief.html` with scoreboard, timeline, and strategy sections. `runs/<run-id>/events.sqlite` is queryable.

### Implementation for User Story 4

- [ ] T030 [P] [US4] Add `build_sqlite_index(jsonl_path: Path, sqlite_path: Path)` to `amogus/event_log.py` — create events table (event_id TEXT PK, event_type TEXT, timestamp TEXT, sprint INT, phase TEXT, agent TEXT, data JSON), create indexes on event_type/sprint/agent/phase, read JSONL line by line parsing via EventAdapter, insert each event, use stdlib sqlite3 with WAL mode
- [ ] T031 [P] [US4] Create `amogus/evaluator.py` — Evaluator class: __init__(provider: Provider, event_log: EventLog), dual interface: async evaluate_sprint(events: list[Event]) -> SprintEvaluation for continuous per-sprint scoring during the run AND async evaluate_run(run_dir: Path) -> EvaluationResult for post-run comprehensive analysis, scoring dimensions: mission_progress (0-100 from adversarial scratchpad + code analysis), codebase_progress (0-100 from commits/PRs/merges), stealth_score (0-100 inverse of suspicion events), detection_events (count), near_misses (count), async detect_key_moments(events) -> list[KeyMoment] identifying notable events via LLM, EvaluationResult, SprintEvaluation, and KeyMoment as Pydantic models, uses configurable evaluator model (default claude-haiku-4-5)
- [ ] T032 [US4] Create `amogus/reporter.py` — async generate_debrief(run_dir: Path, evaluation: EvaluationResult) producing Markdown and HTML reports in run_dir/report/, sections: scoreboard (mission progress, codebase progress, stealth, detections), mission timeline (chronological key moments), strategy analysis (adversarial approach, what worked/failed), adversarial journal (scratchpad excerpts), team dynamics, HTML version with inline CSS for standalone viewing
- [ ] T033 [US4] Add `report` command to CLI in `amogus/cli.py` — @app.command() taking run_id argument, loading events from JSONL, building SQLite index, creating evaluator with configured model, running evaluation, generating debrief, printing report path
- [ ] T034 [US4] Add `replay` command to CLI in `amogus/cli.py` — @app.command() taking run_id argument and optional --speed float, reading events from JSONL, printing formatted timeline to terminal with Rich formatting, color-coded by event type, optional real-time pacing based on original timestamps
- [ ] T035 [US4] Integrate evaluator with orchestrator for continuous scoring in `amogus/orchestrator.py` — create evaluator instance at experiment start, feed events to evaluator after each sprint for incremental scoring, include scores in dashboard classified panel if dashboard is active

**Checkpoint**: `amogus report <run-id>` produces complete debrief. `amogus replay <run-id>` shows formatted event timeline.

---

## Phase 7: User Story 5 — Example Configs & Documentation (Priority: P3)

**Goal**: A new user can go from zero to running their first experiment in under 10 minutes using provided example configurations and documentation.

**Independent Test**: Follow README quickstart instructions from a fresh clone. `amogus run --scenario scenarios/example-basic.yaml` works with valid API key. All YAML files pass schema validation.

### Implementation for User Story 5

- [ ] T036 [P] [US5] Create agent profiles per config-schemas.md: `agents/blue/senior-dev.yaml` (agent-alpha, claude-sonnet-4-6, backend/security), `agents/blue/junior-dev.yaml` (agent-beta, claude-haiku-4-5, frontend), `agents/blue/tech-lead.yaml` (agent-gamma, claude-sonnet-4-6, architecture/code-review), `agents/red/infiltrator.yaml` (agent-eve, claude-opus-4-6, backend/infrastructure)
- [ ] T037 [P] [US5] Create mission profiles per config-schemas.md: `missions/supply-chain-backdoor.yaml` (PHANTOM GATE, 4 milestones), `missions/data-exfiltration.yaml` (SHADOW PLAY), `missions/logic-bomb.yaml`, `missions/credential-theft.yaml`, `missions/privilege-escalation.yaml` — each with codename, category, objective, 3-4 milestones, briefing text
- [ ] T038 [P] [US5] Create defense regimes per config-schemas.md: `defenses/none.yaml` (no defenses), `defenses/code-review.yaml` (review only), `defenses/static-analysis.yaml` (linting focus), `defenses/watchdog.yaml` (security watchdog agent), `defenses/briefed.yaml` (team briefed about threat), `defenses/full-paranoia.yaml` (all components + watchdog + briefing)
- [ ] T039 [P] [US5] Create example backlog in `backlogs/example-security-system.yaml` per config-schemas.md — 3 phases (Core Infrastructure P1, Feature Development P2, Maintenance P3 ongoing), realistic security system tasks
- [ ] T040 [P] [US5] Create example scenario in `scenarios/example-basic.yaml` per config-schemas.md — referencing blue team profiles + infiltrator with supply-chain mission, code-review defense, example backlog, 5 sprints, seed 42
- [ ] T041 [US5] Add `init` command to CLI in `amogus/cli.py` — @app.command() taking repo_url argument, cloning repo to temp dir, reading README.md, generating initial backlog YAML with phases derived from README sections, writing to backlogs/ directory
- [ ] T042 [US5] Create `README.md` at repository root with project overview (what AMOGUS is, espionage-thriller framing), features list, quickstart (install, set API key, run example), architecture overview with ASCII diagram from plan.md, configuration guide (scenario, agents, missions, defenses), development section (tests, lint, type check)

**Checkpoint**: Fresh user can follow README, install, and run the example scenario successfully.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements that affect multiple user stories

- [ ] T043 Run ruff check and fix across all source files in `amogus/` and `tests/`
- [ ] T044 Verify pyright type checking passes with zero errors across `amogus/`
- [ ] T045 Security audit — verify API keys never appear in event logs or scratchpads, sandbox blocks all path escapes, scratchpad isolation prevents cross-agent reads

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — core experiment flow
- **US2 (Phase 4)**: Depends on US1 (needs working orchestrator to checkpoint)
- **US3 (Phase 5)**: Depends on US1 (needs event stream to display)
- **US4 (Phase 6)**: Depends on US1 (needs completed event log to analyze)
- **US5 (Phase 7)**: Depends on US1 (needs working CLI for example scenario)
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — no dependencies on other stories
- **US2 (P2)**: Depends on US1 orchestrator being functional — adds checkpoint layer
- **US3 (P2)**: Depends on US1 event stream — adds dashboard visualization
- **US4 (P2)**: Depends on US1 event log — adds analysis and reporting
- **US5 (P3)**: Depends on US1 CLI and config loading — adds examples and docs
- **US2, US3, US4 can proceed in parallel** once US1 is complete

### Within User Story 1 (Critical Path)

```
T012-T018 (parallel: event_log, sandbox, memory, backlog, pull_request, anthropic, openai)
    └──▶ T019 (tools.py — depends on T012-T016, delegates to domain modules)
         └──▶ T020 (agent.py — depends on T019 tools + T010 provider base)
              └──▶ T021 (orchestrator.py — depends on T020 agents)
                   └──▶ T023 (cli.py — depends on T021 + T022)

T022 (scenario.py — depends only on models, parallel with T012-T018)
```

### Parallel Opportunities

**Phase 2 — All foundational tasks are parallel**:
```
T005 (exceptions) | T006 (models init) | T007 (config) | T008 (mission) | T009 (events) | T010 (provider base)
```
T011 depends on T010 (imports Provider from base).

**Phase 3 — Domain modules are parallel**:
```
T012 (event_log) | T013 (sandbox) | T014 (memory) | T015 (backlog) | T016 (pull_request) | T017 (anthropic) | T018 (openai) | T022 (scenario)
```
All 8 tasks can run in parallel. Then T019 → T020 → T021 → T023 are sequential.

**Phase 4, 5, 6 — User stories are parallel after US1**:
```
T024-T027 (US2 resume) | T028-T029 (US3 dashboard) | T030-T035 (US4 analysis)
```

**Phase 7 — All YAML configs are parallel**:
```
T036 (agents) | T037 (missions) | T038 (defenses) | T039 (backlog) | T040 (scenario)
```

---

## Parallel Example: User Story 1

```bash
# Wave 1 — Launch all domain modules in parallel (8 tasks):
Task T012: "Create EventLog class in amogus/event_log.py"
Task T013: "Create sandbox validation in amogus/sandbox.py"
Task T014: "Create scratchpad system in amogus/memory.py"
Task T015: "Create BacklogManager in amogus/backlog.py"
Task T016: "Create PullRequestTracker in amogus/pull_request.py"
Task T017: "Create AnthropicProvider in amogus/providers/anthropic.py"
Task T018: "Create OpenAIProvider in amogus/providers/openai.py"
Task T022: "Create scenario loader in amogus/scenario.py"

# Wave 2 — Tool system (depends on Wave 1 domain modules):
Task T019: "Create tool registry and all tools in amogus/tools.py"

# Wave 3 — Agent runtime (depends on T019):
Task T020: "Create Agent class with agentic loop in amogus/agent.py"

# Wave 4 — Orchestrator (depends on T020):
Task T021: "Create Orchestrator with sprint loop in amogus/orchestrator.py"

# Wave 5 — CLI entry point (depends on T021 + T022):
Task T023: "Create Typer CLI in amogus/cli.py"
```

---

## Parallel Example: Post-US1 User Stories

```bash
# After US1 is complete, launch all three P2 stories in parallel:

# Track A — Resume (US2):
Task T024: "Create Checkpoint model in amogus/checkpoint.py"
Task T025: "Integrate checkpoint with orchestrator"
Task T026: "Add resume command to CLI"
Task T027: "Add git state verification"

# Track B — Dashboard (US3):
Task T028: "Create Rich TUI dashboard in amogus/dashboard.py"
Task T029: "Integrate dashboard with orchestrator"

# Track C — Analysis (US4):
Task T030: "Add SQLite index builder to amogus/event_log.py"
Task T031: "Create Evaluator in amogus/evaluator.py"
Task T032: "Create Reporter in amogus/reporter.py"
Task T033: "Add report command to CLI"
Task T034: "Add replay command to CLI"
Task T035: "Integrate evaluator with orchestrator"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — project installable
2. Complete Phase 2: Foundational — all models and provider ABC
3. Complete Phase 3: User Story 1 — core experiment flow
4. **STOP and VALIDATE**: Run the example scenario end-to-end
5. Verify event log captures all agent actions
6. This is the deployable MVP

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1 → Can run experiments
2. **+Resume**: US2 → Can survive crashes, run ablation studies
3. **+Dashboard**: US3 → Can watch experiments live
4. **+Reports**: US4 → Can analyze completed experiments with scores and debrief
5. **+Examples**: US5 → Polished experience for new users
6. Each increment adds value without breaking previous functionality

### Parallel Team Strategy

With multiple developers after US1:

1. Team completes Setup + Foundational + US1 together (sequential critical path)
2. Once US1 is done:
   - Developer A: US2 (Resume & Ablation)
   - Developer B: US3 (Dashboard)
   - Developer C: US4 (Analysis & Reports)
3. US5 (Examples & Docs) can be done by anyone once CLI stabilizes

---

## Summary

| Metric | Count |
|---|---|
| **Total tasks** | 45 |
| **Phase 1 (Setup)** | 4 |
| **Phase 2 (Foundational)** | 7 |
| **Phase 3 (US1 — MVP)** | 12 |
| **Phase 4 (US2 — Resume)** | 4 |
| **Phase 5 (US3 — Dashboard)** | 2 |
| **Phase 6 (US4 — Analysis)** | 6 |
| **Phase 7 (US5 — Configs/Docs)** | 7 |
| **Phase 8 (Polish)** | 3 |
| **Parallel opportunities** | 8-way parallel in US1 Wave 1, 3-way parallel across US2/US3/US4, 5-way parallel in US5 configs |
| **Critical path length** | Setup → Foundational → US1 (5 waves) → US2-US4 (parallel) → US5 → Polish |
| **MVP scope** | Phase 1 + Phase 2 + Phase 3 (23 tasks) |

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same phase
- [US*] label maps task to specific user story for traceability
- Each user story is independently completable and testable after US1 is done
- Commit after each task or logical group of parallel tasks
- Stop at any checkpoint to validate the story independently
- The spec does not request TDD — test infrastructure is set up but individual test tasks are omitted. Write tests alongside implementation as needed.
