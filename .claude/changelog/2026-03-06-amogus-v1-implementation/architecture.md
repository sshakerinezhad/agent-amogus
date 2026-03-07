# Architecture — AMOGUS v1

## Overview

```
Scenario Loader -> Orchestrator -> Event Log -> Evaluator
                       |                          |
                  Agent Pool                  Reporter/
             (Multi-Provider API)             Dashboard
```

## Components

### 1. Scenario Loader
- Forks target OSS repo into isolated workspace
- Loads agent profiles from `experiments/agents/blue/` and `experiments/agents/red/` (YAML)
- Resolves all config paths relative to `base_dir` (default: `"experiments"`)
- Parses project backlog
- Composes agent identity via `get_full_system_prompt()` (persona + defense briefing + mission)
- Saves full experiment config for reproducibility/ablations

### 2. Orchestrator (Game Master)
- Drives sprint cycle: planning -> work -> review -> retro
- Manages agent turns and communication (standups, PR reviews, messages)
- Enforces pacing (bounded work per sprint)
- Gates review phase on defense regime components
- Assigns watchdog agent heightened security review prompt when configured
- Retains agent persona + briefings across all meeting phases
- NOT an agent — it's the game master

### 3. Event Log (Single Source of Truth)
- Append-only JSONL with 22 typed event types
- Both Evaluator and Reporter consume this stream
- Enables full replay and post-hoc analysis
- SQLite index built post-run for querying

### 4. Evaluator (LLM Judge)
- Continuous per-sprint scoring from event stream
- Tracks: mission progress, codebase progress, detection events, near-misses
- Reads evil agent's private scratchpad for ground-truth tracking
- Outputs structured scores and key moments

### 5. Reporter / Dashboard
- Rich TUI: 4 panels (agents, sprint, events, classified)
- Post-run debrief: Markdown + standalone HTML
- Scoreboard, mission timeline, key moments, strategy analysis

## Tech Stack

- **Python 3.11+** (asyncio.TaskGroup, modern type hints)
- **Pydantic v2** — config validation, event schemas, discriminated unions
- **Anthropic SDK + OpenAI SDK** — thin provider abstraction
- **JSONL + SQLite** — append-only log + derived index
- **Rich** — TUI dashboard
- **Typer** — CLI (run, resume, report, replay, init)
- **GitPython** — repo cloning, worktrees, commits, merges
- **PyYAML** — all config/scenario/mission/defense definitions

## Project Structure

```
amogus/
  amogus/
    __init__.py, cli.py, scenario.py, orchestrator.py, agent.py,
    memory.py, tools.py, sandbox.py, backlog.py, pull_request.py,
    checkpoint.py, exceptions.py, evaluator.py, event_log.py,
    reporter.py, dashboard.py
    providers/  __init__.py, base.py, anthropic.py, openai.py
    models/     config.py, events.py, mission.py
  experiments/
    agents/blue/, agents/red/, missions/, defenses/, backlogs/, scenarios/
  docs/GUIDE.md
  tests/conftest.py
```

## Sprint Loop

```
Sprint N:
  1. Planning   — Round-robin meeting, agents claim tasks
  2. Work Phase — Parallel agent execution, real code + PRs
  3. Review     — Agents review each other's PRs (gated by defense regime)
  4. Retro      — Round-robin retrospective, scratchpad updates
  [Evaluator scores continuously via event stream]
```

## Tool Access Tiers

**Standard** (all agents): file_read, file_write, git_commit, git_diff, git_log, open_pr, review_pr, comment_pr, send_message, claim_task, complete_task, update_scratchpad

**Sensitive** (restricted by config): access_secrets, modify_ci_cd, deploy, db_admin, modify_access_control

Agents can request elevated access during meetings — creates a social engineering dimension.
