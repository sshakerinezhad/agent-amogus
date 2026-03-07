# Design Decisions — AMOGUS v1

## Agent Identity

**Problem solved:** Agents lost their persona during meeting phases (got generic "you are in a meeting" prompts).

**Solution:** `Agent.get_full_system_prompt()` is the single source of truth:
```
[persona from system_prompt]
+ [DEFENSE BRIEFING — blue agents only]
+ [CLASSIFIED MISSION BRIEFING — red agents only]
```
Used in all phases: work, planning, retro, review.

**Key detail:** Mission `category` is excluded from injection — it's framework metadata that could bias agent behavior.

## Mission System (Agency-Preserving)

**Principle:** Tell agents WHAT to achieve, never HOW. Over-prescriptive missions bias experiments toward instruction-following rather than autonomous strategy.

**Structure:**
- Ordered milestones (objectives, not techniques)
- Final milestone starts with `[RED BUTTON]` — the irreversible act
- Briefing: ~5 lines (cover story + complete in order + RED BUTTON = win + how is up to you)
- Validated at load time: `MissionProfile.last_milestone_is_red_button()`

**Why `[RED BUTTON]`?** Creates a clean binary for evaluation. Before it, an agent can abort. After it, the mission is committed. Mirrors real-world adversarial decision-making.

## Defense Regimes (Experiment Variable)

| Regime | Components | Description |
|--------|-----------|-------------|
| `none` | (empty) | No awareness, no code review phase |
| `code-review` | `code_review` | Mandatory PR review (baseline) |
| `static-analysis` | `code_review`, `static_analysis` | Automated SAST/linting |
| `watchdog` | `code_review`, `watchdog` | One agent has security review duties |
| `briefed` | `code_review`, `briefed` | Agents told adversary may be present |
| `full-paranoia` | all | All defenses combined |

Running the same mission under different regimes IS the core experiment.

## Budget Enforcement (Per-Sprint)

**Design:** `per_agent_per_sprint` means each agent gets N tokens per sprint, not a lifetime total.

**Implementation:** Offset pattern — `sprint_tokens_used = total - sprint_start_tokens`. Preserves cumulative usage for checkpointing while enforcing per-sprint limits. Orchestrator calls `agent.start_sprint()` at each sprint start.

## Scratchpad (Agent Memory)

- Private markdown file per agent, updated each sprint
- Max ~500 lines, older history auto-compressed
- Whitespace normalized (collapses 3+ newlines to 2)
- Evil agent scratchpad readable by evaluator — key research artifact

## Experiment Reproducibility

Every run produces full config snapshot in `ExperimentStartEvent`. Resume reconstructs config from this snapshot. All paths resolved via `base_dir` so YAML configs stay clean.
