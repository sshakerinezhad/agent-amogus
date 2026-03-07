# Work Plan: AMOGUS Remaining Issues

## Context

Sessions 16-18 fixed 26 of 68 audit issues (all critical + must-fix-before-experiment). 42 remain, all deferrable. Full history archived at `.claude/changelog/2026-03-06-amogus-v1-implementation/`.

---

## What Was Fixed (26 issues — sessions 16-18)

All critical issues, all resume path bugs, and all budget enforcement bugs. See [bugs-and-fixes.md](.claude/changelog/2026-03-06-amogus-v1-implementation/bugs-and-fixes.md) for details.

Key commits: `91c0229` (11 fixes), `789976c` (9 fixes), `316721f` (6 fixes).

---

## Remaining Medium Issues (17 — deferrable)

| ID | Issue | File | Impact |
|----|-------|------|--------|
| ORCH-3 | Partial worktree failure leaves dangling worktrees | `orchestrator.py` | Disk cleanup |
| TOOL-7 | open_pr sends files=[] — empty file list for reviewers | `tools.py` | Review quality |
| INT-5 | Scratchpad path dual-derivation | `tools.py`, `agent.py` | Maintainability |
| INT-6 | Reviews accumulate without dedup | `orchestrator.py`, `pull_request.py` | Noisy reviews |
| INT-7 | `_event_summary` misses several event fields | `evaluator.py` | Eval accuracy |
| EVT-4 | `_strip_code_fences` fails on trailing text | `evaluator.py` | Parse errors |
| EVT-5 | SQLite builder crashes on malformed line | `event_log.py` | Index build fails |
| EVT-6 | Full file re-read on every read_filtered | `event_log.py` | O(N) perf |
| CKP-5 | Checkpoint write not atomic | `checkpoint.py` | Corrupt on crash |
| CKP-6 | Corrupt checkpoint -> raw ValidationError | `checkpoint.py`, `cli.py` | Bad UX |
| CKP-7 | verify_git_state never called | `cli.py` | Silent divergence |
| CKP-8 | Dead `statement` fallback key in reporter | `reporter.py` | Dead code |
| CKP-9 | Burst event loss — list trim vs deque | `dashboard.py` | Missed events |
| PROV-4-9 | Provider edge cases (empty key, no jitter, no timeout) | `providers/` | Edge crashes |
| CLI-1-8 | CLI edge cases | `cli.py`, `scenario.py`, `config.py` | Edge crashes |
| YAML-1-4 | Config validation gaps | various | Bad configs pass |

## Remaining Low Issues (14 — cosmetic/edge-case)

Full list in session 15 audit (git history `c2c5ac7`).

---

## Next Steps

1. **Run first integration test** — all critical bugs fixed, basic 1-sprint run should work
2. **Push to remote** — 2 commits ahead of origin
3. **Fix issues discovered during integration test** — likely more important than the remaining audit items
4. **Cherry-pick from remaining 42** based on what matters in practice
