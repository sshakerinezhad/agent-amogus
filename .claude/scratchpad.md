# Scratchpad

## Current Project: AMOGUS

Adversarial Multi-agent Operations for Gauging Undetected Sabotage — an open-source Python framework for running long-horizon adversarial experiments on real codebases with autonomous coding agent teams.

## Session Summary (2026-03-06, session 12)

### What was done

**Executed all 7 steps of the work plan** (`.claude/work-plan.md`) covering 8 structural issues:

1. **Step 1 (Bug Fixes)**: Added exception logging to `tools.py`, normalized whitespace in `memory.py`. Skipped event_log false positive.
2. **Step 2 (Evaluator Default)**: Changed default from `claude-haiku-4-5` → `claude-opus-4-6` in config.py (2 locations), cli.py, README.md, docs/GUIDE.md.
3. **Step 3 (Agent Persona + Defense Regimes)**:
   - Added `defense_briefing` param to Agent
   - Added `get_full_system_prompt()` — single source of truth for persona + briefings
   - Refactored `build_context()` to use it
   - Updated all meeting phases (planning/retro/review) to use per-agent system prompts
   - Added defense components gate in review_phase
   - Added watchdog-specific security review prompt
   - Threaded `defense_briefing` through CLI `_run()` and `_resume()`
4. **Step 4 (Mission Overhaul)**: Added `[RED BUTTON]` validator, lowered min milestones to 1, rewrote all 5 mission YAMLs with agency-preserving briefings.
5. **Step 5 (Directory Restructure)**: Moved agents/, missions/, defenses/, backlogs/, scenarios/ under `experiments/`. Added `base_dir` to ScenarioConfig + ExperimentConfig. Updated scenario.py path resolution. Updated cli.py `init` command.
6. **Step 6 (Target Repo Notice)**: Added REPLACE comments in scenario YAML and docs.
7. **Step 7 (Doc Fixes)**: Fixed dashboard description, clone URL, tech-lead model reference in masterplan.

### Verification Results

- **ruff check**: All passed
- **ruff format**: All formatted
- **pyright**: 0 errors, 0 warnings
- **Schema validation**: All 5 missions pass `[RED BUTTON]` validator
- **Scenario load**: `base_dir: "experiments"` resolves correctly
- **Defense regimes**: All 6 load with correct components/watchdog/briefing
- **Behavioral tests**: Red agent gets mission, blue gets defense briefing, plain gets just system_prompt; category excluded from injection

### Current State

- **Branch**: `001-agent-amogus-v1`
- **PR**: #1 (open, targeting main)
- **All 8 issues implemented and verified**
- **NOT yet committed** — changes ready for review

### Next Steps

1. **Commit** the changes
2. **Unit tests**: Write tests using conftest fixtures
3. **Integration test**: `amogus run --scenario experiments/scenarios/example-basic.yaml` (needs real repo URL)
4. **Merge PR #1** after tests pass
