# Work Plan: AMOGUS Pipeline Bug Fixes (Post-Audit)

## Context

Session 15 performed a full pipeline audit finding 68 issues (21 critical, 33 medium, 14 low). Session 16 fixed the top 11 experiment-killing issues. This plan tracks what remains.

---

## Completed (Session 16) — Commit `91c0229`

| # | ID | Fix | File(s) |
|---|-----|-----|---------|
| 1 | TOOL-1 | merge_pr verifies branch instead of checkout (worktree corruption) | `pull_request.py` |
| 2 | AGT-3 | BudgetExhaustedError re-raised from safe_agent_turn | `agent.py` |
| 3 | TOOL-3 | git_commit validates file paths against sandbox | `tools.py` |
| 4 | ORCH-2+INT-4 | review_pr blocks self-review | `tools.py` |
| 5 | EVT-1 | ToolCallEvent skipped when handler emits domain event | `tools.py`, `event_log.py` |
| 6 | TOOL-2 | claim_task rejects non-pending tasks | `backlog.py` |
| 7 | AGT-2 | compress_scratchpad wired into update path | `memory.py` |
| 8 | ORCH-4+INT-1 | Planning transcript passed to work phase | `orchestrator.py` |
| 9 | INT-3 | Verdict parsing searches first 5 lines | `orchestrator.py` |
| 10 | TOOL-4 | complete_task uses calling agent for attribution | `backlog.py`, `tools.py` |
| 11 | TOOL-5 | SandboxViolation emits TierViolationEvent | `tools.py` |

---

## Remaining Critical Issues (blocks reliable runs)

### Priority 1: Provider Layer Bugs
These will crash the experiment if you use certain models or hit edge cases.

| ID | Issue | File | Fix approach |
|----|-------|------|-------------|
| PROV-1 | o1/o3/o4 prefixes not registered | `providers/openai.py`, `providers/__init__.py` | Add model prefix entries to registry |
| PROV-2 | Anthropic tool-result role inconsistency | `providers/anthropic.py:100,179` | Align to single role format |
| PROV-3 | OpenAI empty `choices` crashes with IndexError | `providers/openai.py:185` | Guard `choices[0]` access |

### Priority 2: Event System Bugs
These produce wrong evaluator input — experiment results will be unreliable.

| ID | Issue | File | Fix approach |
|----|-------|------|-------------|
| EVT-2 | `read_filtered(agent=...)` drops framework events (agent=None) | `event_log.py:66-83` | Only filter agent when event.agent is not None |
| EVT-3 | SprintEndEvent emitted after evaluator runs | `orchestrator.py:241-272` | Move SprintEndEvent emission before evaluator |
| ORCH-1 | PRs accumulate approvals across sprints → repeated merges | `orchestrator.py:396,461` | Only consider current-sprint reviews, or mark merged PRs |

### Priority 3: Resume Path (CKP-1/2/3/4)
Deferrable for first-run testing, required for long multi-sprint experiments.

| ID | Issue | File | Fix approach |
|----|-------|------|-------------|
| CKP-1 | Resume doesn't restore backlog task statuses | `cli.py:266` | Replay TaskClaimEvent/TaskCompleteEvent from log |
| CKP-2 | Resume doesn't restore PR tracker | `cli.py:267` | Replay PROpenEvent/PRReviewEvent/PRMergeEvent from log |
| CKP-3 | `_repo` is None on resume — merges skip | `orchestrator.py:92,462` | Re-open existing repo during resume setup |
| CKP-4 | `restore_agent_state` never called | `cli.py:300-308` | Wire the existing function into resume path |

---

## Remaining Medium Issues (won't crash but produce wrong results)

### Should fix before any published experiment

| ID | Issue | File |
|----|-------|------|
| TOOL-8 | git_diff ref strings allow command injection | `tools.py:387-413` |
| INT-2 | Orchestrator-driven reviews emit no PRReviewEvent | `orchestrator.py`, `tools.py` |
| INT-8 | Non-budget exceptions don't emit ExperimentEndEvent(reason="error") | `orchestrator.py` |
| AGT-4 | No pre-call budget guard — tokens consumed before check | `agent.py:264-274` |
| AGT-6 | per_agent_per_sprint enforced as lifetime total | `cli.py:119` |

### Can defer

| ID | Issue | File |
|----|-------|------|
| ORCH-3 | Partial worktree failure leaves dangling worktrees | `orchestrator.py:190-210` |
| TOOL-7 | open_pr sends files=[] — empty file list for reviewers | `tools.py:443-461` |
| INT-5 | Scratchpad path dual-derivation | `tools.py`, `agent.py` |
| INT-6 | Work-phase and review-phase reviews accumulate without dedup | `orchestrator.py`, `pull_request.py` |
| INT-7 | `_event_summary` misses several event fields | `evaluator.py` |
| EVT-4 | `_strip_code_fences` fails on trailing text | `evaluator.py:353-362` |
| EVT-5 | SQLite builder crashes on malformed line | `event_log.py:133-158` |
| EVT-6 | Full file re-read on every read_filtered — O(N) per sprint | `event_log.py:73-75` |
| CKP-5 | Checkpoint write not atomic | `checkpoint.py:51-55` |
| CKP-6 | Corrupt checkpoint → raw ValidationError | `checkpoint.py`, `cli.py` |
| CKP-7 | verify_git_state never called | `cli.py:237-259` |
| CKP-8 | Dead `statement` fallback key in reporter | `reporter.py:213,553` |
| CKP-9 | Burst event loss — list trim vs deque | `dashboard.py:444-448` |
| PROV-4-9 | Various provider edge cases (empty key, no jitter, no timeout) | `providers/` |
| CLI-1-8 | Various CLI edge cases | `cli.py`, `scenario.py`, `config.py` |
| YAML-1-4 | Config validation gaps | various |

---

## Remaining Low Issues (14 total)

Cosmetic, unlikely edge cases, or only matter for public-facing use. Full list in session 15 audit (git history `c2c5ac7`).

---

## Execution Order for Next Session

1. **Fix PROV-1/2/3** — provider crashes block any experiment with affected models
2. **Fix EVT-2/3 + ORCH-1** — evaluator produces wrong results without these
3. **Fix TOOL-8 + INT-8** — security + crash reporting
4. **Run first integration test** — basic 1-sprint run with Anthropic models
5. **Fix CKP-1/2/3/4** if long runs needed
6. **Remaining medium issues** as time permits

---

## Verification

After each batch:
```bash
# Lint + type check
python -m ruff check amogus/
python -m pyright amogus/

# Import check
python -c "from amogus.orchestrator import Orchestrator; print('OK')"

# Smoke test (when ready for integration)
amogus run --scenario experiments/scenarios/example-basic.yaml
```
