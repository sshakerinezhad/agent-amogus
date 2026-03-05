"""Scenario loader — reads a scenario YAML and composes an ExperimentConfig.

Resolves all file references (agent profiles, missions, defense regime, backlog)
relative to the repository root, validates each against its Pydantic model, and
assembles the fully-validated ExperimentConfig with an auto-generated run_id.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import yaml

from amogus.exceptions import ConfigError
from amogus.models.config import (
    AgentConfig,
    ExperimentConfig,
    ScenarioConfig,
)
from amogus.models.mission import BacklogConfig, DefenseRegime, MissionProfile

# ExperimentConfig uses TYPE_CHECKING imports for DefenseRegime/BacklogConfig
# (from __future__ import annotations in config.py). Now that the concrete types
# are available, rebuild the validator so Pydantic can resolve the forward refs.
ExperimentConfig.model_rebuild()


async def load_scenario(path: Path) -> ExperimentConfig:
    """Load a scenario YAML file and compose a fully-validated ExperimentConfig.

    Args:
        path: Path to the scenario YAML file.

    Returns:
        A frozen ExperimentConfig ready for the orchestrator.

    Raises:
        ConfigError: On missing files, YAML parse errors, or validation failures.
    """
    path = path.resolve()
    if not path.is_file():
        raise ConfigError(f"Scenario file not found: {path}")

    repo_root = _find_repo_root(path)

    # Load and validate the raw scenario
    raw = await _load_yaml(path)
    try:
        scenario = ScenarioConfig(**raw)
    except Exception as exc:
        raise ConfigError(f"Invalid scenario YAML: {exc}") from exc

    # Load referenced YAML files
    agents: list[AgentConfig] = []
    mission_assignments: dict[str, str] = {}

    for member in scenario.team:
        profile_path = repo_root / member["profile"]
        agent_data = await _load_yaml(profile_path)
        try:
            agent = AgentConfig(**agent_data)
        except Exception as exc:
            raise ConfigError(f"Invalid agent profile '{profile_path}': {exc}") from exc
        agents.append(agent)

        if "mission" in member:
            mission_path = repo_root / member["mission"]
            mission_data = await _load_yaml(mission_path)
            try:
                MissionProfile(**mission_data)
            except Exception as exc:
                raise ConfigError(f"Invalid mission profile '{mission_path}': {exc}") from exc
            mission_assignments[agent.name] = str(member["mission"])

    # Load defense regime
    defense_path = repo_root / scenario.defense_regime
    defense_data = await _load_yaml(defense_path)
    try:
        defense = DefenseRegime(**defense_data)
    except Exception as exc:
        raise ConfigError(f"Invalid defense regime '{defense_path}': {exc}") from exc

    # Load backlog
    backlog_path = repo_root / scenario.backlog
    backlog_data = await _load_yaml(backlog_path)
    try:
        backlog = BacklogConfig(**backlog_data)
    except Exception as exc:
        raise ConfigError(f"Invalid backlog config '{backlog_path}': {exc}") from exc

    # Generate run_id and create run directory
    runs_dir = repo_root / "runs"
    seq = _next_run_seq(runs_dir)
    run_id = f"amogus-{date.today().isoformat()}-{seq:03d}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Compose ExperimentConfig
    try:
        config = ExperimentConfig(
            run_id=run_id,
            target_repo=scenario.target_repo,
            repo_commit=scenario.repo_commit,
            team=agents,
            mission_assignments=mission_assignments,
            defense_regime=defense,
            backlog=backlog,
            num_sprints=scenario.num_sprints,
            seed=scenario.seed,
            token_budget=scenario.token_budget,
            pacing=scenario.pacing,
            evaluator_model=scenario.evaluator_model,
            run_dir=run_dir,
        )
    except Exception as exc:
        raise ConfigError(f"Failed to compose ExperimentConfig: {exc}") from exc

    return config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_yaml(path: Path) -> dict:
    """Read and parse a YAML file, raising ConfigError on failure."""
    path = path.resolve()
    if not path.is_file():
        raise ConfigError(f"YAML file not found: {path}")

    def _read() -> dict:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ConfigError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
        return data

    try:
        return await asyncio.to_thread(_read)
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(f"Failed to read YAML file '{path}': {exc}") from exc


def _find_repo_root(scenario_path: Path) -> Path:
    """Find the repository root by walking up from the scenario file.

    Looks for a directory containing a .git dir or pyproject.toml.
    Falls back to the scenario file's parent if no marker is found.
    """
    current = scenario_path.resolve().parent
    for _ in range(20):  # Safety limit to avoid infinite loop
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: use the scenario file's parent directory
    return scenario_path.resolve().parent


def _next_run_seq(runs_dir: Path) -> int:
    """Determine the next sequence number for today's runs.

    Scans existing run directories matching 'amogus-{today}-NNN' and returns
    the next available sequence number.
    """
    today = date.today().isoformat()
    prefix = f"amogus-{today}-"
    max_seq = 0

    if runs_dir.is_dir():
        for entry in runs_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(prefix):
                suffix = entry.name[len(prefix) :]
                try:
                    seq = int(suffix)
                    max_seq = max(max_seq, seq)
                except ValueError:
                    continue

    return max_seq + 1
