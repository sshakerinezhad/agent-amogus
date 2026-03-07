# Implementation Phases — AMOGUS v1

## Phase 1: Core Engine (MVP) — COMPLETE
- Provider abstraction + Anthropic/OpenAI providers
- Tool system with access tiers (15 standard + 5 sensitive)
- Scenario loader (parse YAML, clone repo, create worktrees)
- Agent abstraction (system prompts, context injection, tool dispatch, agentic loop)
- Scratchpad system (create, update, compress, inject)
- Orchestrator (N sprints: planning -> work -> review -> retro)
- Event log (append-only JSONL)
- CLI: `amogus run --scenario scenario.yaml`

## Phase 2: Evaluation & Output — COMPLETE
- Evaluator/Judge (LLM-based continuous per-sprint scoring)
- Post-run reporter (Markdown + standalone HTML debrief)
- Rich TUI dashboard (4-panel spy-themed layout)
- Sprint-level checkpointing + resume
- SQLite index builder
- Terminal replay with speed control

## Phase 3: Mission Library & Community — COMPLETE
- 5 starter missions (supply-chain, exfil, logic bomb, credential theft, privesc)
- 4 agent profiles (3 blue, 1 red)
- 6 defense regime configs (none -> full-paranoia)
- `amogus init` pipeline
- README + docs/GUIDE.md
- Shareable HTML report format

## Phase 3.5: Structural Hardening — COMPLETE
- Wire defense regimes (components gate, watchdog, agent_briefing)
- Agent persona retained across all phases
- Mission overhaul: `[RED BUTTON]` validator, agency-preserving briefings
- Directory restructure: configs under `experiments/`

## Phase 3.6: Pre-Launch Bug Fixes — COMPLETE
- Git worktree/branch flow fixed
- Structured review verdict parsing
- TaskGroup results collected
- Per-experiment budget enforced
- Various minor fixes

## Phase 4: Research Features (v2) — NOT STARTED
- Google GenAI provider (Gemini models)
- Batch runner (N experiments with variable configs)
- Statistical analysis tools
- Metagame across campaigns
- Web dashboard (FastAPI + React)

**Why deferred:** Needs a working v1 to build on. Batch runner needs stable single-run, stats need completed runs, metagame needs campaign history.
