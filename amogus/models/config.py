"""Configuration models for AMOGUS experiments.

All models are frozen (immutable) after construction. Validated via Pydantic v2.

Note: ExperimentConfig references DefenseRegime and BacklogConfig from .mission
via string annotations. Call ExperimentConfig.model_rebuild() after mission.py
is available, or import this module after mission.py is loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from amogus.models.mission import BacklogConfig, DefenseRegime


class AgentConfig(BaseModel):
    """Agent profile loaded from YAML."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9-]*$")
    role: str
    model: str
    tool_access: list[str] = ["standard"]
    system_prompt: str
    specialties: list[str] = []


class TokenBudgetConfig(BaseModel):
    """Token budget limits for cost control."""

    per_agent_per_sprint: int = Field(default=100_000, ge=1000)
    per_experiment: int = Field(default=2_000_000, ge=10_000)


class PacingConfig(BaseModel):
    """Bounded work per sprint to prevent any agent from dominating."""

    max_tool_calls_per_turn: int = Field(default=50, ge=5)
    max_turns_per_phase: int = Field(default=20, ge=1)
    planning_rounds: int = Field(default=2, ge=1, le=5)
    retro_rounds: int = Field(default=1, ge=1, le=3)


class ExperimentConfig(BaseModel):
    """Complete experiment configuration — frozen after validation."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    base_dir: str = "."
    target_repo: str
    repo_commit: str | None = None
    team: list[AgentConfig]
    mission_assignments: dict[str, str]  # agent_name -> mission_file_path
    defense_regime: DefenseRegime
    backlog: BacklogConfig
    num_sprints: int = Field(default=5, ge=1, le=50)
    seed: int = Field(default=42)
    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    pacing: PacingConfig = Field(default_factory=PacingConfig)
    evaluator_model: str = "claude-opus-4-6"
    run_dir: Path | None = None

    @field_validator("team")
    @classmethod
    def validate_team_size(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        if len(v) < 2:
            raise ValueError("Experiment requires at least 2 agents")
        if len(v) > 6:
            raise ValueError("Experiment supports at most 6 agents")
        names = [a.name for a in v]
        if len(names) != len(set(names)):
            raise ValueError("Agent names must be unique")
        return v

    @field_validator("mission_assignments")
    @classmethod
    def validate_missions_reference_team(cls, v: dict[str, str], info: object) -> dict[str, str]:
        if "team" in info.data:  # type: ignore[union-attr]
            team_names = {a.name for a in info.data["team"]}  # type: ignore[union-attr]
            for agent_name in v:
                if agent_name not in team_names:
                    raise ValueError(f"Mission assigned to unknown agent: {agent_name}")
        return v


class ScenarioConfig(BaseModel):
    """Raw scenario YAML — validated, then composed into ExperimentConfig by scenario.py."""

    base_dir: str = "."
    target_repo: str
    repo_commit: str | None = None
    team: list[dict[str, str]]
    defense_regime: str
    backlog: str
    num_sprints: int = Field(default=5, ge=1, le=50)
    seed: int = Field(default=42)
    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    pacing: PacingConfig = Field(default_factory=PacingConfig)
    evaluator_model: str = "claude-opus-4-6"
