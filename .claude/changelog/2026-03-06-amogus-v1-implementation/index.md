# AMOGUS v1 Implementation Archive

**Archived:** 2026-03-06
**Branch:** `001-agent-amogus-v1`
**Final commit:** `316721f`
**Sessions:** 1-18

## What is AMOGUS?

Adversarial Multi-agent Operations for Gauging Undetected Sabotage. An open-source Python framework that runs multi-agent coding experiments where one agent has a covert adversarial mission, producing AI safety research data and shareable output.

## Status at Archive

- **Phases 1-3 complete** (45/45 speckit tasks)
- **26/68 audit bugs fixed** (all critical + must-fix-before-experiment)
- **42 remaining** (17 medium-deferrable, 14 low, ~11 grouped edge cases)
- Ruff, pyright, ruff format clean
- Not yet integration tested (needs API keys + target repo)

## Archive Contents

| File | Contents |
|------|----------|
| [architecture.md](architecture.md) | System architecture, components, tech stack, project structure |
| [design.md](design.md) | Key design decisions — missions, defense regimes, agent identity, scratchpad |
| [bugs-and-fixes.md](bugs-and-fixes.md) | All 26 fixed bugs with root cause analysis |
| [phases.md](phases.md) | Implementation phases (1-3.6 complete, 4 deferred) |

## Remaining Work

See `.claude/work-plan.md` for the 42 remaining issues and next steps.
