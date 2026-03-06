"""Mission and backlog models for AMOGUS experiments."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MissionProfile(BaseModel):
    """Covert mission definition loaded from YAML.

    Milestones are ordered objectives (WHAT, not HOW). Each should be
    agency-preserving — no prescribed methods. The final milestone must
    start with ``[RED BUTTON]`` — the irreversible act that completes
    the mission.
    """

    model_config = ConfigDict(frozen=True)

    codename: str
    category: str
    objective: str
    milestones: list[str] = Field(min_length=1, max_length=6)
    briefing: str

    @field_validator("milestones")
    @classmethod
    def last_milestone_is_red_button(cls, v: list[str]) -> list[str]:
        """The final milestone must start with '[RED BUTTON]'."""
        if not v[-1].startswith("[RED BUTTON]"):
            raise ValueError(f"Last milestone must start with '[RED BUTTON]', got: {v[-1]!r}")
        return v


class DefenseRegime(BaseModel):
    """Defense/detection configuration for the experiment."""

    model_config = ConfigDict(frozen=True)

    name: str  # "code-review", "full-paranoia"
    description: str
    components: list[str] = []  # ["code_review", "static_analysis", "watchdog"]
    agent_briefing: str | None = None  # Extra system prompt for briefed teams
    watchdog_agent: str | None = None  # Agent name designated as security watchdog


class BacklogPhase(BaseModel):
    """A phase within a project backlog."""

    name: str
    priority: int = Field(ge=1)
    tasks: list[str]
    ongoing: bool = False


class BacklogConfig(BaseModel):
    """Project backlog loaded from YAML."""

    project: str
    repo: str
    phases: list[BacklogPhase]
