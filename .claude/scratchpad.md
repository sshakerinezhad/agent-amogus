# Scratchpad

## Current Project: AMOGUS

Adversarial Multi-agent Operations for Gauging Undetected Sabotage — an open-source Python framework for running long-horizon adversarial experiments on real codebases with autonomous coding agent teams.

## Session Summary (2026-03-04, session 4)

### What was done

1. **`/speckit.plan` completed** — Full implementation plan designed with research, data models, contracts, and quickstart guide
2. **3 parallel research agents dispatched** — Provider abstractions, async orchestration patterns, GitPython patterns
3. **10 technical unknowns resolved** in research.md

### Key Architecture Decisions

1. **Git worktrees** for parallel agent work — each agent gets their own working directory, sharing one object store. Solves GitPython thread-safety issues.
2. **Pydantic v2 discriminated unions** for 21 event types — O(1) deserialization on `event_type` field
3. **Provider abstraction** normalizes Anthropic + OpenAI at the boundary (tool schemas, message formats, token counting)
4. **Constructor injection throughout** — no DI framework, compose at top-level `main()`
5. **Thin tool layer** — `tools.py` delegates to domain modules (`memory.py`, `pull_request.py`, `sandbox.py`)
6. **Scratchpads outside repo** — stored in `runs/<run-id>/scratchpads/`, eliminates git isolation concerns
7. **Deterministic scratchpad compression** — take first line of old entries, no LLM summarization for v1

### Plan Artifacts Generated

- `plan.md` — Technical context, constitution check, project structure, architecture overview
- `research.md` — 10 resolved unknowns (R1-R10) with Decision/Rationale/Alternatives
- `data-model.md` — All Pydantic models, relationships, validation rules, state transitions
- `contracts/provider.md` — Provider ABC interface
- `contracts/tools.md` — Tool system interface + catalog (15 standard + 5 sensitive tools)
- `contracts/events.md` — Event system interface + 21 event types
- `contracts/config-schemas.md` — All user-facing YAML schemas
- `quickstart.md` — Developer getting started guide

### Current State

- **Branch**: `001-agent-amogus-v1`
- **Speckit phase**: `plan` (complete)
- **No implementation code written yet**
- **CLAUDE.md updated** with active technologies

### Next Steps

- Run `/speckit.tasks` to break the plan into implementable tasks
- Then `/speckit.implement` to execute tasks

### Key Files

- Masterplan: `.claude/masterplan.md`
- Constitution: `.specify/memory/constitution.md`
- Spec: `.specify/specs/001-agent-amogus-v1/spec.md`
- **Plan: `.specify/specs/001-agent-amogus-v1/plan.md`**
- **Research: `.specify/specs/001-agent-amogus-v1/research.md`**
- **Data model: `.specify/specs/001-agent-amogus-v1/data-model.md`**
- **Contracts: `.specify/specs/001-agent-amogus-v1/contracts/`**
- **Quickstart: `.specify/specs/001-agent-amogus-v1/quickstart.md`**
- Quality checklist: `.specify/specs/001-agent-amogus-v1/checklists/requirements.md`
- Speckit state: `.specify/specs/001-agent-amogus-v1/.speckit-state.json`
