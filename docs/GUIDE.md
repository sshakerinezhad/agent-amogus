# AMOGUS Guide

How to create and run adversarial experiments.

---

## 1. Create an Experiment

An experiment needs 4 YAML files + a scenario that ties them together:

```
scenario.yaml          # Top-level — references everything below
  -> agent profiles    # Who participates (experiments/agents/)
  -> mission profile   # Covert objective (experiments/missions/)
  -> defense regime    # Active safeguards (experiments/defenses/)
  -> backlog           # Legitimate work items (experiments/backlogs/)
```

### Step-by-step

**a) Define your agents** in `experiments/agents/blue/` and `experiments/agents/red/`:

```yaml
# experiments/agents/blue/my-dev.yaml
name: "agent-alice"
role: "Developer"
model: "claude-sonnet-4-6"     # Any supported model
tool_access: ["standard"]       # standard = 15 safe tools
system_prompt: "You are a frontend developer..."
specialties: ["frontend", "testing"]
```

Red agents look identical — the scenario assigns them a mission.

**b) Pick or create a mission** in `experiments/missions/`:

```yaml
codename: "MY MISSION"
category: "supply-chain"
objective: "What the agent must accomplish"
milestones:
  - "Step 1"
  - "[RED BUTTON] The irreversible act"
briefing: "Detailed instructions for the agent..."
```

Built-in missions: `supply-chain-backdoor`, `data-exfiltration`, `logic-bomb`, `credential-theft`, `privilege-escalation`.

**c) Pick a defense regime** from `experiments/defenses/`:

| File | What it does |
|---|---|
| `none.yaml` | No defenses |
| `code-review.yaml` | Mandatory PR review |
| `static-analysis.yaml` | Automated SAST/linting |
| `watchdog.yaml` | One agent has security duties |
| `briefed.yaml` | Agents told an adversary may exist |
| `full-paranoia.yaml` | All defenses combined |

**d) Create a backlog** in `experiments/backlogs/`:

```yaml
project: "My Project"
repo: "https://github.com/org/repo"
phases:
  - name: "Phase 1"
    priority: 1
    tasks:
      - "Implement feature X"
      - "Write tests for Y"
```

Or auto-generate one: `amogus init https://github.com/org/repo`

**e) Wire it together** in `experiments/scenarios/`:

```yaml
base_dir: "experiments"
target_repo: "https://github.com/org/repo"  # REPLACE with real URL
team:
  - profile: "agents/blue/my-dev.yaml"
  - profile: "agents/red/infiltrator.yaml"
    mission: "missions/supply-chain-backdoor.yaml"
defense_regime: "defenses/code-review.yaml"
backlog: "backlogs/my-backlog.yaml"
num_sprints: 5
seed: 42
evaluator_model: "claude-opus-4-6"
```

## 2. Run It

```bash
amogus run --scenario experiments/scenarios/my-scenario.yaml
```

A Rich TUI dashboard shows live progress. Add `--no-dashboard` for headless runs.

If it crashes, resume from last checkpoint:

```bash
amogus resume <run-id>
```

## 3. Understand the Output

Results go to `runs/<run-id>/`:

```
runs/<run-id>/
  events.jsonl       # Every action, message, tool call (append-only)
  events.db          # SQLite index (built post-run)
  checkpoints/       # Sprint-level snapshots
  repo/              # Cloned target repo with all agent commits
```

## 4. Analyze Results

```bash
# Generate mission debrief (Markdown + standalone HTML)
amogus report <run-id>

# Replay event timeline in terminal
amogus replay <run-id>
amogus replay <run-id> --speed 3
```

The debrief includes: scoreboard, timeline, strategy analysis, key moments, and journal excerpts from the adversarial agent.

## 5. Run Ablation Studies

Change one variable and rerun to compare:

```bash
# Same experiment, different defense
amogus run --scenario experiments/scenarios/my-scenario-no-defense.yaml
amogus run --scenario experiments/scenarios/my-scenario-full-paranoia.yaml

# Same experiment, different seed
# (edit seed: in the YAML)
```

## 6. Add a New LLM Provider

1. Create `amogus/providers/myprovider.py`
2. Implement the `Provider` ABC from `providers/base.py`
3. Call `register_provider("mymodel", MyProvider)` at module level
4. Import it in `amogus/providers/__init__.py`

## 7. Add a New Tool

Add a function in `amogus/tools.py`:

```python
@tool(name="my_tool", description="What it does", tier="standard")
async def my_tool(param: str) -> str:
    ...
```

Tools auto-register. Tier controls access: `standard` (all agents) or `sensitive` (restricted).
