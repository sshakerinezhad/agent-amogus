# experiments/

Configuration files for AMOGUS experiments.

| Directory    | Contains                                    |
|-------------|---------------------------------------------|
| `agents/`    | Agent profile YAMLs (blue team + red team) |
| `missions/`  | Covert mission briefings for red agents    |
| `defenses/`  | Defense regime configurations              |
| `backlogs/`  | Project backlog definitions                |
| `scenarios/` | Experiment scenarios combining the above   |

**Quick start:** copy `scenarios/example-basic.yaml`, set `target_repo` to a real Git URL, and run `amogus run --scenario experiments/scenarios/your-scenario.yaml`.
