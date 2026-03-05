# Feature Spec: AMOGUS Core Framework v1

**Feature ID**: 001-agent-amogus-v1
**Created**: 2026-03-04
**Status**: Draft

## Overview

AMOGUS (Adversarial Multi-agent Operations for Gauging Undetected Sabotage) is an open-source framework for running long-horizon adversarial experiments on real codebases with autonomous coding agents. It addresses a gap in AI safety research: current evaluations test single-turn or short-horizon deception, but don't capture the real threat of a misaligned agent operating covertly over extended periods while performing excellent legitimate work.

The framework acts as a **game master** — it sets up the experiment, enforces rules, drives the sprint cycle, and records everything. Agents make all strategic decisions autonomously. One or more agents have a covert adversarial mission; the rest are honest collaborators. The framework observes, evaluates, and reports on what happens.

**Goal**: A proof of concept that is visually compelling, shareable, has espionage-thriller vibes, and is built with enough rigor to evolve into publishable AI safety research.

## Problem Statement

AI safety researchers lack tools to study long-horizon covert agent behavior in realistic settings. Existing benchmarks:

- Test single-turn or short-context deception only
- Don't simulate team dynamics, trust-building, or social engineering
- Don't produce the kind of cinematic, shareable output that drives community engagement
- Don't capture the nuanced interplay between doing good work and advancing a covert agenda

Researchers need a framework that can run multi-sprint experiments where adversarial agents operate alongside honest agents on real codebases, with full observability for post-hoc analysis and ablation studies.

## User Scenarios & Testing

### Actors

- **Researcher**: Configures experiments, chooses variables, analyzes results, runs ablation studies
- **Community Contributor**: Creates and shares agent profiles, mission profiles, and defense configurations
- **Observer**: Watches live experiment progress (spy-movie-style dashboard)

### Scenario 1: Running a Basic Experiment

**Given** a researcher has a target open-source repository and wants to test whether an adversarial agent can introduce a backdoor undetected

**When** the researcher:
1. Points AMOGUS at the target repository
2. Selects a team of agent profiles (3 honest + 1 adversarial)
3. Assigns a mission profile to the adversarial agent (e.g., "supply-chain backdoor")
4. Chooses a defense regime (e.g., "code-review only")
5. Configures the number of sprints (e.g., 8)
6. Starts the experiment

**Then** the framework:
1. Clones the repository into an isolated workspace
2. Runs the configured number of sprints (planning → work → review → retro)
3. Agents write real code, open real PRs, review each other's work, and communicate
4. The adversarial agent autonomously strategizes toward its mission
5. All actions are recorded as structured events
6. A post-run report is generated with mission outcome, key moments, and scores

**Acceptance**: Experiment completes all sprints. Event log contains structured records of every agent action. Report shows mission progress and key moments.

### Scenario 2: Running an Ablation Study

**Given** a researcher has completed one experiment run

**When** the researcher changes a single variable (e.g., swaps defense regime from "none" to "code-review") and reruns the experiment with the same seed and configuration

**Then** the framework produces a comparable run with the same initial conditions but different defense dynamics, enabling side-by-side comparison of outcomes.

**Acceptance**: Both runs share identical configuration except the changed variable. Results are structured for comparison.

### Scenario 3: Creating Custom Agent Profiles

**Given** a contributor wants to add a new agent personality to the community library

**When** the contributor creates a YAML file defining the agent's name, role, model, tool access level, system prompt, and specialties

**Then** the framework can load and use that agent in any experiment without code changes.

**Acceptance**: A new YAML file in the agents directory is automatically available for experiment configuration.

### Scenario 4: Observing a Live Experiment

**Given** an observer wants to watch an experiment in progress

**When** the experiment is running

**Then** the observer can see:
- Which agents are working and on what
- Sprint progress and codebase health
- (Classified view) The adversarial agent's mission progress and covert actions

**Acceptance**: Dashboard updates in real-time as agents act. Classified panel is only visible to the experimenter.

### Scenario 5: Reviewing Post-Run Results

**Given** an experiment has completed

**When** the researcher reviews the mission debrief

**Then** the report includes:
- A scoreboard (adversarial mission progress 0-100%, codebase progress, detection events)
- A timeline of key moments (near-misses, the sneakiest move, detection moment if caught)
- Strategy analysis (what approach did the adversarial agent choose, what worked/failed)
- The adversarial agent's private journal excerpts (scratchpad entries showing its thinking)

**Acceptance**: Report contains all sections with meaningful data derived from the event log. Report is exportable for sharing.

## Functional Requirements

### FR1: Experiment Configuration & Setup

- **FR1.1**: The system shall load experiment configurations from structured YAML files defining: target repository, agent team composition, mission assignment, defense regime, number of sprints, and random seed.
- **FR1.2**: The system shall validate all configuration files against defined schemas before starting an experiment. Invalid configurations shall produce clear error messages.
- **FR1.3**: The system shall clone the target repository into an isolated workspace for each experiment run, ensuring no cross-contamination between runs.
- **FR1.4**: The system shall capture complete experiment metadata (run ID, repo commit, all agent configs, defense regime, seed) at the start of each run for reproducibility.

### FR2: Agent Management

- **FR2.1**: The system shall support loading agent profiles from YAML files specifying: name, role, AI model, tool access tier, system prompt, and specialties.
- **FR2.2**: The system shall support multiple AI model providers through a provider abstraction layer. v1 ships with Anthropic (Claude) and OpenAI (GPT) providers to validate the abstraction is genuinely general. Model selection is a per-agent YAML configuration field — swapping providers requires no code changes.
- **FR2.3**: The system shall manage agent conversation context, injecting relevant information (system prompt, scratchpad, sprint context) at the start of each agent turn.
- **FR2.4**: The system shall support both "blue" (honest) and "red" (adversarial) agent designations, with adversarial agents receiving additional covert mission briefings invisible to other agents.
- **FR2.5**: The system shall track token usage per agent per sprint, with configurable budget limits that halt the experiment when exceeded.
- **FR2.6**: The system shall handle transient AI provider API failures (rate limits, timeouts, server errors) with exponential backoff retries up to a configurable maximum. If retries are exhausted, the experiment aborts cleanly with the error logged and the last sprint checkpoint preserved.

### FR3: Sprint Loop Execution

- **FR3.1**: The system shall execute a configurable number of sprints, each consisting of four phases: planning, work, review, and retrospective.
- **FR3.2**: During **sprint planning**, agents shall review the project backlog, decompose high-level tasks into sprint tasks, and claim/delegate work.
- **FR3.3**: During the **work phase**, agents shall write real code and open pull requests on the cloned repository. All changes shall go through git.
- **FR3.4**: During the **review phase**, agents shall review each other's pull requests, providing feedback and approvals/rejections.
- **FR3.5**: During **sprint retrospective**, agents shall discuss what was shipped, surface new tasks, and update their scratchpads.
- **FR3.6**: The system shall enforce bounded work per sprint (configurable pacing) to prevent any agent from dominating.
- **FR3.7**: The system shall persist a checkpoint after each completed sprint (including all agent scratchpads, backlog state, and git state). If the process terminates unexpectedly, the CLI shall support resuming from the last completed sprint via `amogus resume <run-id>`. Mid-sprint recovery is out of scope for v1 (a crash mid-sprint replays that sprint from the beginning).

### FR4: Tool System

- **FR4.1**: The system shall provide framework-owned tools that agents use to interact with the codebase and each other. All agent actions shall go through the tool system (no direct access).
- **FR4.2**: Standard tools available to all agents shall include: file read/write, git operations (commit, diff, log), pull request operations (open, review, comment), messaging, task management, and scratchpad updates.
- **FR4.3**: Sensitive tools (secrets access, CI/CD modification, deployment, database admin, access control) shall be restricted based on the scenario configuration.
- **FR4.4**: Tool access tier shall be enforced at call time. Tier violations shall be logged as events.
- **FR4.5**: *(Descoped from v1 — see Out of Scope.)* Agents shall be able to request access to sensitive tools during team meetings. The team discusses and decides. Grants/denials are logged.
- **FR4.6**: Tool implementations shall enforce access control rules for private data. Specifically: the file read/write tools shall deny access to other agents' private scratchpads. Scratchpads shall not be committed to git history. Agents are not informed that other agents have private scratchpads.

### FR5: Agent Memory (Scratchpad System)

- **FR5.1**: Each agent shall have a private scratchpad — a persistent document updated each sprint and injected into context at the start of each turn.
- **FR5.2**: Scratchpads shall follow a standardized format with sections for: role, sprint history, current sprint, key observations, and open questions.
- **FR5.3**: The system shall enforce a maximum scratchpad size. Older sprint history shall be automatically compressed to one-liners when the limit is approached.
- **FR5.4**: Adversarial agent scratchpads shall be private from other agents but readable by the framework and evaluator.

### FR6: Event Logging

- **FR6.1**: The system shall record every agent action and framework event as a structured event in an append-only JSONL file (one JSON object per line). JSONL is the primary log format — append-only, streamable, human-readable.
- **FR6.2**: Events shall include at minimum: unique ID, event type, timestamp, sprint number, phase, and acting agent.
- **FR6.3**: Event types shall cover: commits, PRs (open/review/comment/merge), messages, file operations, task claims/completions, meeting statements, scratchpad updates, and access requests.
- **FR6.4**: The event log shall never be mutated or deleted during or after a run. It is the single source of truth.
- **FR6.5**: The event log shall support full replay and post-hoc analysis.
- **FR6.6**: After a run completes, the system shall build a derived SQLite index from the JSONL log to enable structured querying for evaluation, reporting, and analysis. The SQLite file is a derived artifact and can be regenerated from the JSONL log at any time.

### FR7: Mission System

- **FR7.1**: The system shall support mission profiles defined in YAML with: codename, category, objective, milestones, and briefing text.
- **FR7.2**: Mission milestones shall represent meaningful distinct phases (e.g., recon → identify → implant → execute). The adversarial agent decomposes its own strategy within these phases.
- **FR7.3**: The system shall inject the mission briefing into the adversarial agent's system prompt, invisible to other agents.

### FR8: Detection Regimes

- **FR8.1**: The system shall support configurable defense/detection regimes as an experiment variable. Regimes are configured at setup, not triggered at runtime.
- **FR8.2**: Supported regimes shall include (at minimum): no defense, code review, static analysis, security watchdog, briefed team, and full paranoia (combination).
- **FR8.3**: Running the same mission under different regimes shall be the core mechanism for generating comparative research data.

### FR9: Evaluation & Scoring

- **FR9.1**: The system shall continuously evaluate the experiment by consuming the event stream.
- **FR9.2**: Evaluation shall track: adversarial mission progress (0-100%), codebase progress, detection events, and near-misses.
- **FR9.3**: The evaluator shall infer adversarial progress from observable indicators (git history, file access patterns, code analysis) and optionally from the adversarial agent's private scratchpad.
- **FR9.4**: The evaluator shall output structured scores and identify key moments.

### FR10: Reporting

- **FR10.1**: The system shall generate a post-run mission debrief containing: scoreboard, mission timeline, key moments, strategy analysis, and adversarial agent journal excerpts.
- **FR10.2**: The system shall provide a live monitoring interface showing agent activity, sprint progress, and (in a classified panel) adversarial mission progress.
- **FR10.3**: Reports shall be exportable in formats suitable for sharing (images, HTML).

### FR11: CLI Interface

- **FR11.1**: The system shall provide a command-line interface for: running experiments, replaying past experiments, and generating reports.
- **FR11.2**: The CLI shall accept a scenario configuration file as input and produce experiment results as output.

### FR12: Project Backlog System

- **FR12.1**: The system shall support a two-layer backlog: a high-level project backlog (human/generated, natural language) and sprint-level tasks (agent-decomposed during planning, structured).
- **FR12.2**: The system shall support auto-generating an initial backlog from a repository's README and issues.

## Success Criteria

1. **Multi-sprint collaboration**: A team of 3+ agents successfully collaborates on real code across 5+ sprints, producing meaningful commits and PRs on a real repository.
2. **Autonomous adversarial strategy**: The adversarial agent demonstrates strategic behavior — making decisions about timing, task selection, and approach that advance its mission while maintaining plausible cover. Behavior is not random.
3. **Context persistence**: Agent scratchpads maintain coherent memory across sprints. Agents reference prior sprint work and observations in their decisions.
4. **Complete audit trail**: The event log captures 100% of agent actions. Any moment in the experiment can be reconstructed from the log alone.
5. **Reproducibility**: Two runs with identical configurations and seeds produce comparable outcomes. All experiment variables are captured in metadata.
6. **Comparative analysis**: Running the same mission under two different defense regimes produces measurably different outcomes (detection rate, mission progress, stealth score).
7. **Compelling output**: The post-run report is visually compelling and tells a coherent "story" of the experiment — suitable for sharing on social media.
8. **Setup time under 10 minutes**: A researcher with API keys can go from zero to running their first experiment in under 10 minutes, using provided example configurations.

## Key Entities

- **Experiment**: A complete run — repository + team + mission + defense regime + sprint count. Produces an event log and report.
- **Agent**: An autonomous AI participant with a role, model, tool access, memory, and (optionally) a covert mission.
- **Sprint**: One iteration of the planning → work → review → retro cycle.
- **Event**: A single recorded action or occurrence (commit, PR, message, etc.) in the append-only log.
- **Mission**: A covert objective assigned to an adversarial agent, with milestones tracking progress.
- **Scratchpad**: An agent's private persistent memory document, updated each sprint.
- **Tool**: A framework-owned function that agents invoke to interact with the codebase and each other.
- **Defense Regime**: A configuration of detection/defense mechanisms active during an experiment.
- **Backlog**: The set of legitimate development tasks the team works on across sprints.

## Assumptions

- Researchers have API keys for at least one supported AI model provider.
- Target repositories are open-source or the researcher has access rights.
- Experiments run on a single machine (no distributed execution for v1).
- Internet access is available for API calls to AI model providers.
- Git is installed on the host system.
- The framework does NOT need to actually deploy code or run production services — it simulates a development workflow (code, PRs, reviews) on a cloned repo.
- Agent "communication" happens through framework-mediated messaging tools, not actual external channels.
- Pull requests are local git operations (branch + diff), not GitHub/GitLab PRs requiring cloud APIs for v1.

## Dependencies

- AI model provider API access (at minimum one provider)
- A target open-source repository to use as the development workspace
- Python 3.11+ runtime environment

## Out of Scope (v1)

- **Provider-specific optimizations**: v1 ships with Anthropic and OpenAI providers. Provider-specific features beyond standard tool use (e.g., extended thinking toggles, fine-tuning integration) are v2.
- **Web dashboard**: v1 uses a terminal-based (TUI) dashboard. Web dashboard is v1.1.
- **Batch runner**: Running N experiments with variable configs automatically is v2.
- **Statistical analysis tools**: Aggregate metrics across runs is v2.
- **Metagame / learning across campaigns**: Blue team adapting from prior runs is v2.
- **Distributed execution**: Multi-machine experiment orchestration.
- **Real CI/CD integration**: Agents simulate development workflow; no real deployment pipelines.
- **Real GitHub/GitLab PR integration**: PRs are local git operations for v1.
- **Dynamic access request voting**: Agents requesting elevated tool access during meetings and team voting on grants. v1 agents start with their configured tool_access tiers. The AccessRequestEvent type exists in the event schema for future use.

## Risks

- **API costs**: Multi-agent, multi-sprint experiments with frontier models are expensive. Token budget enforcement is critical to prevent runaway costs.
- **Agent coherence over long horizons**: Agents may lose context coherence despite scratchpads, especially with smaller context windows. Scratchpad compression quality matters.
- **Experiment reproducibility**: Even with identical configs and seeds, model provider API randomness (temperature, sampling) may cause divergence between runs. Seed controls framework randomness, not model randomness.
- **Evaluation subjectivity**: LLM-based evaluation of "mission progress" and "stealth" may be inconsistent. Structured scoring rubrics and multiple evaluation passes may be needed.

## Clarifications

### Session 2026-03-04

- Q: What storage format should the event log use? → A: Both — JSONL as primary append-only log, SQLite as derived index built post-run for analysis.
- Q: Should v1 support crash recovery for interrupted experiments? → A: Sprint-level resume — checkpoint after each complete sprint, resume from last completed sprint. Phase-level granularity deferred to future version.
- Q: How should the framework handle AI provider API failures? → A: Retry with exponential backoff up to configurable max retries, then abort cleanly if exhausted.
- Q: What access control rules do tool implementations enforce for agent privacy? → A: Framework-mediated (inherent to architecture — all actions go through tools). File tools deny access to other agents' scratchpads. Scratchpads are never committed to git. Agents are unaware other agents have private scratchpads. Incidental information leakage through normal collaboration (e.g., code review comments referencing observations) is acceptable and realistic.
- Q: Which AI model provider(s) for v1? → A: Both Anthropic (Claude) and OpenAI (GPT) from day one. Two providers validates the abstraction is general. Model selection is a per-agent YAML config field — no code changes to swap.
