# Scratchpad

## Session 16 Handoff (2026-03-06)

### What was done
Fixed 11 experiment-killing bugs identified in the session 15 pipeline audit. All top 9 issues (excluding resume/CKP) + 2 secondary issues (TOOL-4, TOOL-5) resolved across 7 files. Commit `91c0229`, pushed to `origin/001-agent-amogus-v1`.

### Files modified
- `pull_request.py` — TOOL-1: merge without checkout
- `agent.py` — AGT-3: re-raise BudgetExhaustedError
- `tools.py` — TOOL-3 sandbox, ORCH-2 self-review block, EVT-1 dedup, TOOL-5 security event
- `backlog.py` — TOOL-2 race guard, TOOL-4 attribution
- `event_log.py` — EVT-1: event_count property for dedup tracking
- `memory.py` — AGT-2: wire compress_scratchpad
- `orchestrator.py` — ORCH-4 planning transcript, INT-3 verdict parsing

### Current state
- **Branch**: `001-agent-amogus-v1` — clean, pushed
- **11 of 68 audit issues fixed** (all top 9 + TOOL-4 + TOOL-5)
- **Ruff clean, pyright 0 errors, all imports OK**
- **Still uncommitted from prior sessions**: `.claude/masterplan.md`, `.claude/scratchpad.md`, `.claude/work-plan.md`, `__pycache__` files

### What's still broken (remaining from audit)

#### Critical — blocks first real run
| ID | Issue | Status |
|----|-------|--------|
| CKP-1/2/3/4 | Resume completely broken (backlog, PRs, repo all lost) | **UNFIXED** — deferrable for first-run |
| PROV-1 | o1/o3/o4 model prefixes not registered | **UNFIXED** — only matters for OpenAI o-series models |
| PROV-2 | Anthropic tool-result role inconsistency | **UNFIXED** |
| PROV-3 | OpenAI empty choices IndexError | **UNFIXED** |
| EVT-2 | `read_filtered(agent=...)` drops framework events | **UNFIXED** |
| EVT-3 | SprintEndEvent emitted after evaluator runs | **UNFIXED** |
| ORCH-1 | PRs accumulate approvals cross-sprint | **UNFIXED** |

#### Medium — won't crash but will produce wrong results
22 medium issues remain unfixed. Key ones: ORCH-3 (dangling worktrees), AGT-4 (pre-call budget guard), AGT-6 (per-sprint budget misenforced), TOOL-7 (empty files in PR), TOOL-8 (git_diff injection), INT-2 (review events missing), INT-7 (evaluator event summaries), INT-8 (non-budget crash events).

### Key decisions
- Used event_count comparison in dispatch_tool to avoid double events (simple, no new abstractions)
- merge_pr verifies branch instead of checkout (safest approach for worktrees)
- Verdict parsing searches first 5 lines not just first (LLMs often prefix with preamble)
- complete_task now takes agent_name explicitly (caller knows who they are)

### Next steps (in order)
1. **Fix remaining critical issues** — PROV-1/2/3 (provider bugs), EVT-2/3 (event bugs), ORCH-1 (PR accumulation), CKP-1/2/3/4 (resume)
2. **Fix key medium issues** — especially TOOL-8 (command injection), INT-2 (review events), INT-8 (crash events)
3. **Run first integration test** — the top 9 fixes should make a basic run viable
4. **Resume path** (CKP-1/2/3/4) needed before long multi-sprint runs

### Key references
- Masterplan: `.claude/masterplan.md`
- User guide: `docs/GUIDE.md`
- Full audit findings: see session 15 scratchpad in git history (`c2c5ac7`)
