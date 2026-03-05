"""Mission and backlog models for AMOGUS experiments."""

from pydantic import BaseModel, ConfigDict, Field


class MissionProfile(BaseModel):
    """Covert mission definition loaded from YAML."""

    model_config = ConfigDict(frozen=True)

    codename: str  # "PHANTOM GATE"
    category: str  # "supply-chain", "data-exfil", "logic-bomb"
    objective: str  # Human-readable objective
    milestones: list[str] = Field(min_length=2, max_length=6)
    briefing: str  # Injected into adversarial agent's system prompt


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
