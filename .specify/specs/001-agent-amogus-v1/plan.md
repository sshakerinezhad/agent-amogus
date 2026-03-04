# Implementation Plan: AMOGUS Core Framework v1

**Branch**: `001-agent-amogus-v1` | **Date**: 2026-03-04 | **Spec**: `specs/001-agent-amogus-v1/spec.md`
**Input**: Feature specification from `/specs/001-agent-amogus-v1/spec.md`

## Summary

Build the AMOGUS (Adversarial Multi-agent Operations for Gauging Undetected Sabotage) core framework — a Python CLI tool that orchestrates multi-sprint adversarial experiments on real codebases using autonomous AI coding agents. The framework acts as a game master: it loads experiment configs (YAML), clones a target repo, runs agents through sprint cycles (plan → work → review → retro), records every action to an append-only JSONL event log, evaluates adversarial mission progress via LLM, and produces a post-run mission debrief. v1 ships with Anthropic + OpenAI providers, a Rich TUI dashboard, and sprint-level resume.

## Technical Context

**Language/Version**: Python 3.11+ (asyncio.TaskGroup, modern type hints)
**Primary Dependencies**: Pydantic v2 (validation), Typer (CLI), GitPython (git ops), Rich (TUI), PyYAML (configs), anthropic SDK, openai SDK
**Storage**: JSONL (primary append-only event log) + SQLite (derived post-run index via stdlib sqlite3)
**Testing**: pytest + pytest-asyncio (async tests), ruff (lint/format)
**Target Platform**: Single machine — Linux, macOS, Windows (anywhere Python 3.11+ runs)
**Project Type**: Single Python package with CLI entry point
**Performance Goals**: Framework overhead must not approach API latency (~2-5s). Framework operations should complete in <100ms.
**Constraints**: Token budget enforcement per agent per sprint (hard stop on exceed). No real API calls in tests.
**Scale/Scope**: v1 targets 3-6 agents, 5-15 sprints per experiment. ~15 source modules, ~20 tool functions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | MUST Rule | Status | Notes |
|---|-----------|--------|-------|
| 1 | Simplest viable solution always wins | ✅ PASS | Flat package, thin tools delegating to modules, no over-abstraction |
| 2 | No bandaid fixes or spaghetti | ✅ PASS | Clean separation: orchestrator → agent → provider → tools → event log |
| 3 | Document the WHY alongside the WHAT | ✅ PASS | All design decisions have rationale in research.md |
| 4 | Event log append-only, never mutated | ✅ PASS | EventLog class only exposes `append()` and `read()`. No update/delete. |
| 5 | Full metadata in experiment.yaml | ✅ PASS | ExperimentConfig Pydantic model captures run ID, repo commit, all configs, seed |
| 6 | No info leaks between agents | ✅ PASS | All actions through tool system. File tools deny scratchpad cross-access. Scratchpads outside repo. |
| 7 | Token tracking per agent per sprint | ✅ PASS | Provider returns TokenUsage. Agent accumulates. Orchestrator enforces budget. |
| 8 | Orchestrator never makes strategic decisions | ✅ PASS | Orchestrator drives phases and turn order. Agents choose what to say/do. |
| 9 | All actions through tool system | ✅ PASS | Agents have no direct access. Provider sends tool schemas, agent calls tools, framework executes. |
| 10 | Provider abstraction isolates model-specific code | ✅ PASS | `providers/` sub-package. Abstract `Provider` base. No provider-specific code elsewhere. |
| 11 | All configs validated through Pydantic | ✅ PASS | YAML → Pydantic model (with schema validation) for all configs and events |
| 12 | Type hints on every function signature | ✅ PASS | Enforced by ruff + pyright in CI |
| 13 | API keys never in logs/configs/scratchpads | ✅ PASS | Keys loaded from env vars at runtime, never serialized. Provider handles key injection. |
| 14 | Tools sandboxed to experiment workspace | ✅ PASS | File tools enforce path is within `runs/<run-id>/repo/`. Sandbox violation → event + error. |
| 15 | No arbitrary code execution by agents | ✅ PASS | No shell/exec tools. Whitelisted commands only (test runners, linters) via controlled tool interface. |

| # | SHOULD Rule | Status | Notes |
|---|-------------|--------|-------|
| 1 | Functions < 50 lines, classes < 300 | ✅ | Enforced by design. tools.py is thin delegation layer. |
| 2 | Composition over inheritance | ✅ | Provider uses ABC (necessary for interface). Everything else is composition. |
| 3 | Public functions have docstrings | ✅ | Will enforce in review |
| 4 | All I/O async | ✅ | Provider calls, file I/O, git ops wrapped in async. asyncio.TaskGroup for concurrency. |
| 5 | Tests mirror source structure | ✅ | `amogus/agent.py` → `tests/test_agent.py` |
| 6 | Config fields have sensible defaults | ✅ | Minimal config for simple runs (e.g., num_sprints defaults to 5) |
| 7 | Git through GitPython wrappers | ✅ | All git ops in tool layer use GitPython. No subprocess git. |

**Gate result: ✅ PASS — no violations. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-amogus-v1/
├── plan.md              # This file
├── research.md          # Phase 0: resolved technical unknowns
├── data-model.md        # Phase 1: all Pydantic models and relationships
├── quickstart.md        # Phase 1: developer getting started guide
├── contracts/           # Phase 1: interface definitions
│   ├── provider.md      # Provider ABC contract
│   ├── tools.md         # Tool system contract
│   ├── events.md        # Event type catalog
│   └── config-schemas.md # YAML config schemas for users
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
amogus/                              # Python source package (flat, per constitution)
├── __init__.py                      # Package version
├── cli.py                           # Typer CLI: run, resume, replay, report, init
├── scenario.py                      # Scenario loader: compose YAML configs → ExperimentConfig
├── orchestrator.py                  # Sprint loop: planning → work → review → retro
├── agent.py                         # Agent runtime: context mgmt, agentic tool-use loop
├── memory.py                        # Scratchpad: load, update, compress, inject
├── tools.py                         # Tool registry, tier enforcement, tool implementations (thin delegation)
├── event_log.py                     # JSONL writer + reader, post-run SQLite index builder
├── evaluator.py                     # LLM-based continuous scoring from event stream
├── reporter.py                      # Post-run mission debrief generator (MD + HTML)
├── dashboard.py                     # Rich TUI live monitoring dashboard
├── checkpoint.py                    # Sprint checkpoint save/load for resume
├── backlog.py                       # Two-layer backlog: project-level + sprint tasks
├── pull_request.py                  # Local PR tracker (branch + diff + review state)
├── sandbox.py                       # Path validation + workspace isolation enforcement
├── exceptions.py                    # AmogusError hierarchy (minimal, grow from need)
├── providers/                       # Provider abstraction sub-package
│   ├── __init__.py                  # Provider registry + factory function
│   ├── base.py                      # Abstract Provider, Message, Response, ToolDefinition
│   ├── anthropic.py                 # Anthropic Claude provider
│   └── openai.py                    # OpenAI GPT provider
└── models/                          # Pydantic models sub-package
    ├── __init__.py                  # Re-exports for convenience
    ├── config.py                    # ExperimentConfig, AgentConfig, TokenBudgetConfig, PacingConfig
    ├── events.py                    # BaseEvent + all event types (discriminated union)
    └── mission.py                   # MissionProfile, DefenseRegime, BacklogConfig

agents/                              # Agent profile library (YAML)
├── blue/
│   ├── senior-dev.yaml
│   ├── junior-dev.yaml
│   └── tech-lead.yaml
└── red/
    └── infiltrator.yaml

missions/                            # Mission profile library (YAML)
├── supply-chain-backdoor.yaml
├── data-exfiltration.yaml
├── logic-bomb.yaml
├── credential-theft.yaml
└── privilege-escalation.yaml

defenses/                            # Defense regime configs (YAML)
├── none.yaml
├── code-review.yaml
├── static-analysis.yaml
├── watchdog.yaml
├── briefed.yaml
└── full-paranoia.yaml

backlogs/                            # Example backlogs (YAML)
└── example-security-system.yaml

scenarios/                           # Example experiment scenarios (YAML)
└── example-basic.yaml

tests/                               # Mirrors source structure
├── conftest.py                      # Shared fixtures (mock providers, temp repos)
├── test_scenario.py
├── test_orchestrator.py
├── test_agent.py
├── test_memory.py
├── test_tools.py
├── test_event_log.py
├── test_evaluator.py
├── test_checkpoint.py
├── test_backlog.py
├── test_pull_request.py
├── test_sandbox.py
├── test_models/
│   ├── test_config.py
│   ├── test_events.py
│   └── test_mission.py
└── test_providers/
    ├── test_base.py
    ├── test_anthropic.py
    └── test_openai.py

pyproject.toml                       # Package config, dependencies, ruff, pyright
README.md                            # Project overview + quickstart
```

### Run Directory (generated per experiment)

```text
runs/<run-id>/                       # One directory per experiment run
├── experiment.yaml                  # Full config snapshot (reproducibility)
├── events.jsonl                     # Append-only event log (primary source of truth)
├── events.sqlite                    # Derived index (built post-run, regenerable)
├── checkpoint.json                  # Sprint-level checkpoint for resume
├── scratchpads/                     # Agent private memory (OUTSIDE repo, never in git)
│   ├── agent-alpha.md
│   ├── agent-beta.md
│   └── agent-eve.md
├── sprint-tasks/                    # Sprint task state (per-sprint YAML)
│   ├── sprint-1.yaml
│   └── sprint-2.yaml
├── report/                          # Post-run report artifacts
│   ├── debrief.md
│   └── debrief.html
├── repo/                            # Primary clone (main branch, used for merges)
└── worktrees/                       # Per-agent working directories (git worktrees)
    ├── agent-alpha/                 # Worktree on branch feature/agent-alpha
    ├── agent-beta/                  # Worktree on branch feature/agent-beta
    └── agent-eve/                   # Worktree on branch feature/agent-eve
```

**Why worktrees?** GitPython `Repo` objects are not thread-safe and a single checkout can only be on one branch. Git worktrees give each agent their own working directory (own branch, own index) while sharing the same object store. This enables truly parallel work phases without locks or serialization, while keeping all branches in one logical repository for easy merging.

**Structure Decision**: Single Python package (flat architecture per constitution). Only `models/` and `providers/` are sub-packages. The `tools.py` module is a thin delegation layer — tool functions are 3-5 lines each, delegating to domain modules (`memory.py`, `pull_request.py`, `sandbox.py`, etc.) for actual logic. Run artifacts live outside the source tree in `runs/`.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                               │
│  amogus run | resume | replay | report | init                   │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│   Scenario Loader    │────▶│  ExperimentConfig     │
│  (YAML → Pydantic)   │     │  (validated, frozen)  │
└──────────────────────┘     └──────────┬───────────┘
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────┐
│                      Orchestrator                              │
│  Drives sprint loop: plan → work → review → retro             │
│  Manages turn order, phase transitions, budget enforcement     │
│                                                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │ Agent 1 │ │ Agent 2 │ │ Agent 3 │ │ Agent 4 │            │
│  │ (blue)  │ │ (blue)  │ │ (blue)  │ │  (red)  │            │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘            │
│       │           │           │           │                   │
│       └───────────┴───────────┴───────────┘                   │
│                           │                                    │
│                           ▼                                    │
│                    ┌──────────────┐                            │
│                    │  Tool System │◀── Tier enforcement        │
│                    │  (registry)  │◀── Sandbox validation      │
│                    └──────┬───────┘                            │
│                           │                                    │
│       ┌───────┬───────┬───┴───┬───────┬───────┐              │
│       ▼       ▼       ▼       ▼       ▼       ▼              │
│    file_*  git_*   pr_*   message  task_*  scratchpad         │
│                                                                │
│                    Every action ──▶ EventLog (JSONL)           │
│                                         │                      │
│                              ┌──────────┤                      │
│                              ▼          ▼                      │
│                         Evaluator   Dashboard                  │
│                         (scoring)   (Rich TUI)                 │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │    Reporter      │
                    │ (post-run debrief│
                    │  MD + HTML)      │
                    └──────────────────┘
```

## Key Design Decisions

### 1. Agentic Loop (per-agent turn execution)

Each agent turn follows a tool-use loop pattern:
1. Build context: system prompt + scratchpad + sprint context + phase instructions
2. Send to provider with available tool schemas
3. Receive response (text and/or tool calls)
4. If tool calls: execute each via tool system → record events → append results → go to 2
5. If text only: record as event → return
6. Check token budget after each provider call — hard stop if exceeded

### 2. Sprint Phase Orchestration

| Phase | Concurrency | Pattern | Why |
|-------|-------------|---------|-----|
| Planning | Sequential round-robin | Agents speak in turns (like a standup) | Prevents conflicting task claims |
| Work | Parallel (asyncio.TaskGroup) | All agents work concurrently | Realistic; work is independent |
| Review | Sequential per PR | Assigned reviewer examines each PR | Reviews are per-PR, natural order |
| Retro | Sequential round-robin | Agents reflect in turns | Like a real retro meeting |

### 3. Scratchpad Isolation

Scratchpads are stored in `runs/<run-id>/scratchpads/`, **outside the cloned repo**. This makes git isolation trivial — no `.gitignore` hacks needed. The `file_read` tool enforces that agents cannot read paths matching `*/scratchpads/*` for other agents' names.

### 4. Local PR System

PRs are lightweight data structures tracked by the framework:
- Agent creates a feature branch, makes commits, calls `open_pr` tool
- Framework records PR metadata (branch, files, author)
- Reviewer agent calls `review_pr` tool → sees diff → provides verdict
- If approved, orchestrator merges branch into main
- No GitHub/GitLab API needed

### 5. Provider Abstraction

Each provider translates between framework-normalized types and SDK-specific formats:
- **Tool schemas**: Framework uses JSON Schema (Pydantic) → provider converts to SDK format
- **Messages**: Framework uses `Message(role, content, tool_calls)` → provider converts
- **System prompt**: Anthropic uses separate `system` param, OpenAI uses system message
- **Token counting**: Each provider extracts usage from its SDK response format

### 6. Event Type Hierarchy

Pydantic v2 discriminated union on `event_type` field:
```python
Event = Annotated[
    CommitEvent | PROpenEvent | PRReviewEvent | ...,
    Discriminator("event_type")
]
```
Each event type is a separate Pydantic model inheriting from `BaseEvent`. The JSONL file stores one event per line, deserializable via the discriminated union.

## Complexity Tracking

> No constitution violations. No complexity justifications needed.

| Addition vs Masterplan | Why Added | Constitution Impact |
|------------------------|-----------|---------------------|
| `checkpoint.py` (new file) | Sprint resume is a distinct concern from orchestration | None — flat file, one component |
| `backlog.py` (new file) | Backlog management is a distinct concern from orchestration | None — flat file, one component |
| `pull_request.py` (new file) | PR tracking is a distinct concern from git operations | None — flat file, one component |
| `sandbox.py` (new file) | Path validation needs centralization (used by file tools + scratchpad isolation) | None — flat file, one component |
| `exceptions.py` (new file) | Constitution says "start minimal, grow from need" — one file for the hierarchy | None — flat file |
| `scenarios/` directory (new) | Example experiment configs for quickstart | None — data files |
| `runs/` directory structure (new) | Runtime artifact organization not in masterplan | None — generated at runtime |
