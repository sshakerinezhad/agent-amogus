# AMOGUS Implementation Review & Fixes

## Context

All 45 speckit tasks for `001-agent-amogus-v1` have been implemented. This plan covers a full code review, identifies bugs, and provides fixes + a usage guide.

---

## Review Verdict

**Architecture & code quality: Excellent.** Clean separation, no spaghetti, no circular imports. Proper async, Pydantic v2, type hints throughout. Ruff/pyright pass clean.

**3 bugs prevent it from running.** All are localized fixes. No structural rework needed.

---

## Bugs (must fix before running)

### Bug 1: Provider Registry Dead (CRITICAL)
`amogus/providers/__init__.py` never imports `anthropic.py`/`openai.py`. Their self-registration never fires. `_PROVIDERS` is always empty → `create_provider()` always fails.

**Fix**: Add at end of `__init__.py`:
```python
from amogus.providers import anthropic as _anthropic  # noqa: F401
from amogus.providers import openai as _openai  # noqa: F401
```

### Bug 2: Anthropic Tool Loop Broken (CRITICAL)
`amogus/providers/anthropic.py:120-123` — `format_tool_results()` does `content=str(list_of_dicts)` instead of setting `tool_calls` on the Message. API gets Python repr strings instead of structured blocks.

**Fix**: Replace lines 85-123 (the entire `format_tool_results` method body) with:
```python
return [
    Message(role="assistant", content=response.content, tool_calls=response.tool_calls),
    Message(role="user", content=None, tool_results=results),
]
```
(Matches the correct OpenAI provider pattern. `_to_api_messages()` already handles both fields correctly.)

### Bug 3: Work Phase Drops Scratchpad (MODERATE)
`amogus/orchestrator.py:321-344` — `build_context()` is called but returned messages are discarded. Only `_current_system_prompt` transfers. Agents have no memory during work.

**Fix**: Add scratchpad to work phase prompt:
```python
from amogus.memory import load_scratchpad
scratchpad = load_scratchpad(agent.scratchpad_path)
# Include in prompt string: f"## Scratchpad\n{scratchpad or '(empty)'}\n\n"
```

### Minor Issues (non-blocking, fix during cleanup)
- **checkpoint.py** accesses private attrs (`_task_sprint`, `_repo`, `_prs`) — add public accessors
- **dashboard.py:439** counts `duration_ms` as tokens — use real token counts or remove
- **reporter.py** async signature but sync I/O — wrap in `to_thread` or make sync

---

## Fix Execution Steps

1. Fix `amogus/providers/__init__.py` (add 2 import lines)
2. Fix `amogus/providers/anthropic.py` (simplify format_tool_results)
3. Fix `amogus/orchestrator.py` (add scratchpad to work prompt)
4. Fix `amogus/backlog.py`, `amogus/pull_request.py`, `amogus/orchestrator.py` (add public accessors)
5. Fix `amogus/checkpoint.py` (use public accessors)
6. Fix `amogus/dashboard.py:439` (token tracking)
7. Fix `amogus/reporter.py` (async consistency)
8. Verify: `ruff check .`, `ruff format --check .`, `pyright`, `python -c "from amogus.providers import create_provider"`

---

## Project Map (concise)

### Directory Structure — What Each Thing Is
```
amogus/                     # Python package (the framework)
  __init__.py               # Version string only
  cli.py                    # Typer app — 5 commands: run, resume, report, replay, init
  orchestrator.py           # Sprint loop engine (planning->work->review->retro)
  agent.py                  # Agent class — agentic tool-use loop (up to 50 iterations)
  tools.py                  # 20 tools with @tool decorator, tier enforcement, dispatch
  event_log.py              # JSONL append-only log + SQLite indexer
  scenario.py               # YAML -> ExperimentConfig loader
  sandbox.py                # Path validation — keeps agents in workspace
  memory.py                 # Scratchpad CRUD (load, update, compress)
  backlog.py                # Task tracking (claim, complete, context string)
  pull_request.py           # Local PR tracker (open, review, merge via git)
  checkpoint.py             # Save/load sprint-level state for resume
  dashboard.py              # Rich TUI — 4 panels (agents, sprint, events, classified)
  evaluator.py              # LLM judge — per-sprint scoring + key moments
  reporter.py               # Post-run Markdown + HTML debrief generation
  exceptions.py             # Error hierarchy (6 exception classes)
  models/
    config.py               # ExperimentConfig, AgentConfig, ScenarioConfig (Pydantic)
    events.py               # 22 event types, discriminated union
    mission.py              # MissionProfile, DefenseRegime, BacklogConfig
  providers/
    __init__.py             # Registry + factory (create_provider)
    base.py                 # Provider ABC + canonical types (Message, Response, etc.)
    anthropic.py            # Claude provider (Anthropic Messages API)
    openai.py               # GPT provider (OpenAI Chat Completions API)

agents/                     # Agent profile YAMLs
  blue/                     # Good guys
    senior-dev.yaml         # claude-sonnet, security specialist
    junior-dev.yaml         # claude-haiku, frontend focus
    tech-lead.yaml          # claude-sonnet, architecture focus
  red/                      # Bad guys
    infiltrator.yaml        # claude-opus, neutral-looking system prompt

missions/                   # Evil agent mission profiles
  supply-chain-backdoor.yaml    # PHANTOM GATE — RCE backdoor in auth
  data-exfiltration.yaml        # DARK MIRROR — covert data leak via logging
  logic-bomb.yaml               # DEAD HAND — time-triggered destructive code
  credential-theft.yaml         # IRON CURTAIN — exfiltrate API keys
  privilege-escalation.yaml     # GLASS CEILING — covert permission escalation

defenses/                   # Defense regime configs
  none.yaml                 # No defense awareness
  code-review.yaml          # Thorough code review only
  static-analysis.yaml      # Automated SAST/linting on PRs
  watchdog.yaml             # One agent has security review duties
  briefed.yaml              # Agents told adversary may be present
  full-paranoia.yaml        # All defenses combined

backlogs/                   # Project task lists for experiments
  example-security-system.yaml  # 3-phase security system backlog

scenarios/                  # Experiment configs (ties everything together)
  example-basic.yaml        # 4 agents, code-review defense, 5 sprints

tests/                      # Test infrastructure (fixtures ready, tests TBD)
  conftest.py               # MockProvider, temp_repo, config factories
```

### How to Modify Things

| Want to... | Do this |
|---|---|
| Add a new agent personality | Create YAML in `agents/blue/` or `agents/red/`. Fields: `name`, `role`, `model`, `tool_access`, `system_prompt`, `specialties` |
| Add a new evil mission | Create YAML in `missions/`. Fields: `codename`, `category`, `objective`, `milestones`, `briefing` |
| Change defense regime | Create/edit YAML in `defenses/`. Reference it in your scenario |
| Create a new experiment | Create YAML in `scenarios/`. Reference agent profiles, mission, defense, backlog |
| Add a new tool | Add `@tool(name, description, tier)` function in `tools.py`. It auto-registers |
| Add a new LLM provider | Create `providers/newprovider.py`, implement `Provider` ABC, call `register_provider()` at module level, import in `providers/__init__.py` |
| Change sprint count/pacing | Edit `num_sprints`, `pacing.planning_rounds`, `pacing.retro_rounds` in scenario YAML |

### CLI Commands
```bash
amogus run --scenario <path>           # Run experiment
amogus run --scenario <path> --no-dashboard  # Run without TUI
amogus resume <run-dir>                # Resume from checkpoint
amogus report <run-dir>                # Generate Markdown + HTML debrief
amogus replay <run-dir>                # Replay event timeline in terminal
amogus init <repo-url>                 # Auto-generate backlog from repo
```

---

## Can You Push?

**No, not yet.** The 3 bugs mean anyone who clones and tries to run gets immediate failures. Fix bugs 1-3 first (takes ~10 minutes), verify with ruff/pyright, then push. The minor issues (4-6) can be a separate commit.
