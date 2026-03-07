# Bugs Found & Fixed — AMOGUS v1

## Summary

68 issues found across audits. 26 fixed (all critical + must-fix). 42 remaining (deferrable).

---

## Post-Implementation Review (6 bugs, sessions 10-11)

### Critical
1. **Provider registry dead** — `providers/__init__.py` never imported provider modules, so self-registration never fired. Fix: explicit imports.
2. **Anthropic tool loop broken** — `format_tool_results()` passed Python repr strings instead of structured data. Fix: match OpenAI provider pattern.
3. **Work phase drops scratchpad** — `build_context()` return value discarded. Fix: inject scratchpad into work phase prompt.

### Minor
4. **checkpoint.py accessed private attrs** — Fix: added public accessors.
5. **Dashboard counted duration_ms as tokens** — Fix: removed incorrect accumulation.
6. **Reporter async/sync mismatch** — Fix: wrapped in `asyncio.to_thread`.

---

## Structural Audit (8 issues, session 12)

1. **Defense regimes were dead code** — Pydantic models populated but never read by runtime. Fix: wired components gate, watchdog prompt, agent_briefing injection.
2. **Agent persona lost during meetings** — Generic "you are in a meeting" prompts replaced identity. Fix: `get_full_system_prompt()`.
3. **Missions over-prescriptive** — Told agents specific techniques. Fix: agency-preserving briefings + `[RED BUTTON]` validator.
4. **Config dirs cluttered repo root** — Fix: moved under `experiments/` with `base_dir` resolution.
5. **Tool exceptions swallowed** — Fix: `logger.exception()` before returning error.
6. **Scratchpad whitespace accumulation** — Fix: `re.sub(r"\n{3,}", "\n\n", content)`.
7. **Evaluator model too weak** — Fix: default `claude-opus-4-6` (was haiku).
8. **Minor doc fixes** — clone URL, dashboard description, scenario paths.

---

## Pre-Launch Audit (7 bugs, sessions 13-14)

1. **[SHOWSTOPPER] Git worktree/branch/PR/merge flow broken** — Detached HEAD, invented branch names, merge crashes. Fix: `git worktree add -b work/<agent>` + auto-detect branch in `open_pr`.
2. **Review verdict gameable** — `"approve" in text.lower()` matched anywhere. Fix: `VERDICT: approve|reject|comment` prefix parsing.
3. **Work phase errors silently dropped** — TaskGroup results never collected. Fix: inspect results, log warnings.
4. **Per-experiment budget never enforced** — Only per-agent checked. Fix: sum all agents after work phase.
5. **Merge failure missing traceback** — Fix: `exc_info=True`.
6. **Duplicate `_find_task` method** — Fix: removed pointless indirection.

---

## Pipeline Audit (26 more fixes, sessions 16-18)

### Session 16 — Commit `91c0229` (11 fixes)
| ID | Fix |
|----|-----|
| TOOL-1 | merge_pr verifies branch instead of checkout |
| AGT-3 | BudgetExhaustedError re-raised from safe_agent_turn |
| TOOL-3 | git_commit validates file paths against sandbox |
| ORCH-2+INT-4 | review_pr blocks self-review |
| EVT-1 | ToolCallEvent skipped when handler emits domain event |
| TOOL-2 | claim_task rejects non-pending tasks |
| AGT-2 | compress_scratchpad wired into update path |
| ORCH-4+INT-1 | Planning transcript passed to work phase |
| INT-3 | Verdict parsing searches first 5 lines |
| TOOL-4 | complete_task uses calling agent for attribution |
| TOOL-5 | SandboxViolation emits TierViolationEvent |

### Session 17 — Commit `789976c` (9 fixes)
| ID | Fix |
|----|-----|
| PROV-1 | Register o1/o3/o4 model prefixes |
| PROV-2 | Anthropic tool-result role alignment |
| PROV-3 | Guard empty choices in OpenAI response |
| EVT-2 | Preserve framework events (agent=None) in filtered queries |
| EVT-3 | SprintEndEvent before evaluator |
| ORCH-1 | Current-sprint-only approvals for merge |
| INT-2 | Emit PRReviewEvent for orchestrator-driven reviews |
| INT-8 | Catch-all ExperimentEndEvent(reason="error") |
| TOOL-8 | Validate git ref strings against safe pattern |

### Session 18 — Commit `316721f` (6 fixes)
| ID | Fix |
|----|-----|
| AGT-4 | Pre-call budget guard before provider.complete() |
| AGT-6 | Per-sprint budget via start_sprint() offset pattern |
| CKP-1 | Restore backlog task statuses from checkpoint |
| CKP-2 | PullRequestTracker.restore_from_checkpoint() |
| CKP-3 | Open existing repo on resume |
| CKP-4 | Wire restore_agent_state() into resume path |

---

## Patterns / Root Causes

- **Self-registration needs explicit imports** — modules don't auto-load
- **Pydantic models != runtime wiring** — declaring a field doesn't mean it's used
- **Multi-phase pipelines need end-to-end testing** — worktree -> branch -> PR -> merge was never tested as a flow
- **Budget checks must fire BEFORE consumption** — not after
- **Resume paths need full state restoration** — fresh objects lose progress
- **Substring matching is gameable** — use structured parsing for verdicts
