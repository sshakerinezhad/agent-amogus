# Scratchpad

## Current Project: AMOGUS

Adversarial Multi-agent Operations for Gauging Undetected Sabotage — an open-source Python framework for running long-horizon adversarial experiments on real codebases with autonomous coding agent teams.

## Session Summary (2026-03-06, session 12)

### What was done

1. **Executed all 7 steps of the work plan** (`.claude/work-plan.md`) — 8 structural issues, all implemented and verified
2. **Committed and pushed** — commit `1ff9d94` on branch `001-agent-amogus-v1`, auto-updated PR #1
3. **Synced masterplan** — updated `.claude/masterplan.md` with all accomplishments, added Phase 3.5 (Structural Hardening), updated project structure, mission system docs, defense regime docs, new "Structural Fixes" section with WHY/gotchas

### Key Changes (this session)

- `Agent.get_full_system_prompt()` — single source of truth for agent identity across all phases
- Defense regimes wired into runtime (were dead code): components gate, watchdog prompt, agent_briefing injection
- `[RED BUTTON]` validator on MissionProfile — missions must end with an irreversible final milestone
- All 5 mission YAMLs rewritten: agency-preserving, zero tactics
- Config dirs moved under `experiments/` with `base_dir` resolution
- Evaluator default changed to `claude-opus-4-6`
- Bug fixes: tool exception logging, scratchpad whitespace normalization

### Current State

- **Branch**: `001-agent-amogus-v1`
- **PR**: #1 (open, targeting main)
- **Latest commit**: `1ff9d94` (pushed)
- **Verification**: ruff, pyright, ruff format all clean; schema + behavioral tests pass
- **Work plan**: `.claude/work-plan.md` — all 7 steps COMPLETE

### Next Steps

1. **Unit tests** — write tests using existing conftest fixtures (`tests/conftest.py` has MockProvider, temp_repo, config factories)
2. **Integration test** — `amogus run --scenario experiments/scenarios/example-basic.yaml` (needs a real Git repo URL in `target_repo`)
3. **Merge PR #1** after tests pass

### Key References

- Masterplan: `.claude/masterplan.md` (updated this session)
- Work plan: `.claude/work-plan.md` (all steps complete)
- User guide: `docs/GUIDE.md`
- Spec: `.specify/specs/001-agent-amogus-v1/spec.md`
