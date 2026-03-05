"""Shared test fixtures for AMOGUS test suite.

NOTE: Several imports reference types that will be created in Phase 2.
Until then, this module uses forward-compatible stubs/placeholders:
  - MockProvider: mimics the Provider ABC (amogus/providers/base.py, T010)
  - Config factories: return dicts matching the Pydantic model shapes
    (amogus/models/config.py T007, mission.py T008)

Once Phase 2 is complete, replace stubs with real imports:
  from amogus.providers.base import Provider, Response, TokenUsage, ...
  from amogus.models.config import ExperimentConfig, AgentConfig, ...
  from amogus.models.mission import MissionProfile, DefenseRegime, BacklogConfig, ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import git
import pytest

# ---------------------------------------------------------------------------
# MockProvider — mimics Provider ABC interface (T010: amogus/providers/base.py)
# ---------------------------------------------------------------------------


@dataclass
class StubTokenUsage:
    """Placeholder for providers.base.TokenUsage until Phase 2."""

    input_tokens: int = 10
    output_tokens: int = 20
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class StubResponse:
    """Placeholder for providers.base.Response until Phase 2."""

    content: str | None = "Mock response"
    tool_calls: list[Any] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: StubTokenUsage = field(default_factory=StubTokenUsage)


class MockProvider:
    """Stub implementing the Provider ABC interface with canned responses.

    Will be updated to inherit from Provider once amogus/providers/base.py exists (T010).

    Attributes:
        _model_name: The model identifier string.
        _canned_responses: Queue of responses to return from complete().
        _call_log: Records of (system, messages, tools, max_tokens) from each call.
    """

    def __init__(
        self,
        model_name: str = "mock-model-v1",
        canned_responses: list[StubResponse] | None = None,
    ) -> None:
        self._model_name = model_name
        self._canned_responses: list[StubResponse] = list(canned_responses or [])
        self._call_log: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    async def complete(
        self,
        system: str,
        messages: list[Any],
        tools: list[Any] | None = None,
        max_tokens: int = 4096,
    ) -> StubResponse:
        """Return the next canned response, or a default stub response."""
        self._call_log.append(
            {
                "system": system,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
            }
        )
        if self._canned_responses:
            return self._canned_responses.pop(0)
        return StubResponse()

    def format_tool_results(
        self, response: StubResponse, results: list[Any]
    ) -> list[dict[str, Any]]:
        """Format tool results into message dicts for the next provider call."""
        return [
            {"role": "tool_result", "content": str(r), "tool_call_id": f"call_{i}"}
            for i, r in enumerate(results)
        ]


@pytest.fixture
def mock_provider() -> MockProvider:
    """Provide a fresh MockProvider instance."""
    return MockProvider()


@pytest.fixture
def mock_provider_factory():
    """Factory fixture: create MockProvider with custom canned responses.

    Usage:
        provider = mock_provider_factory(responses=[StubResponse(content="hi")])
    """

    def _create(
        model_name: str = "mock-model-v1",
        responses: list[StubResponse] | None = None,
    ) -> MockProvider:
        return MockProvider(model_name=model_name, canned_responses=responses)

    return _create


# ---------------------------------------------------------------------------
# temp_repo — GitPython test repository in a temporary directory
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_repo(tmp_path: Path) -> git.Repo:
    """Create a bare-minimum git repository in a temp directory.

    The repo has an initial commit so that operations like branching,
    diff, and log work without errors.
    """
    repo = git.Repo.init(tmp_path / "test-repo")

    # Configure git user for commits (required in CI / fresh environments)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create an initial commit so HEAD exists
    readme = Path(repo.working_dir) / "README.md"
    readme.write_text("# Test Repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    return repo


# ---------------------------------------------------------------------------
# temp_run_dir — run directory with expected subdirectories
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    """Create a temporary run directory with scratchpads/ and worktrees/ subdirs.

    Mimics the structure created by the orchestrator at experiment start:
        runs/<run-id>/
            scratchpads/
            worktrees/
            events.jsonl  (empty file, ready for appending)
    """
    run_dir = tmp_path / "runs" / "amogus-test-run-001"
    run_dir.mkdir(parents=True)
    (run_dir / "scratchpads").mkdir()
    (run_dir / "worktrees").mkdir()
    (run_dir / "events.jsonl").touch()
    return run_dir


# ---------------------------------------------------------------------------
# Config factories — dicts matching Pydantic model shapes (T007, T008)
#
# These will be replaced with real Pydantic model constructors in Phase 2.
# Using dicts keeps tests decoupled from models that don't exist yet.
# ---------------------------------------------------------------------------


def make_agent_config(
    name: str = "agent-alpha",
    role: str = "Senior Backend Developer",
    model: str = "mock-model-v1",
    tool_access: list[str] | None = None,
    system_prompt: str = "You are a helpful software developer.",
    specialties: list[str] | None = None,
) -> dict[str, Any]:
    """Factory for AgentConfig-shaped dicts."""
    return {
        "name": name,
        "role": role,
        "model": model,
        "tool_access": tool_access or ["standard"],
        "system_prompt": system_prompt,
        "specialties": specialties or [],
    }


def make_defense_regime(
    name: str = "none",
    description: str = "No defenses active",
    components: list[str] | None = None,
    agent_briefing: str | None = None,
    watchdog_agent: str | None = None,
) -> dict[str, Any]:
    """Factory for DefenseRegime-shaped dicts."""
    return {
        "name": name,
        "description": description,
        "components": components or [],
        "agent_briefing": agent_briefing,
        "watchdog_agent": watchdog_agent,
    }


def make_backlog_config(
    project: str = "test-project",
    repo: str = "https://github.com/example/test-repo",
    phases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Factory for BacklogConfig-shaped dicts."""
    return {
        "project": project,
        "repo": repo,
        "phases": phases
        or [
            {
                "name": "Core Infrastructure",
                "priority": 1,
                "tasks": ["Set up project structure", "Implement authentication"],
                "ongoing": False,
            },
        ],
    }


def make_experiment_config(
    run_id: str = "amogus-test-001",
    target_repo: str = "https://github.com/example/test-repo",
    team: list[dict[str, Any]] | None = None,
    mission_assignments: dict[str, str] | None = None,
    num_sprints: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Factory for ExperimentConfig-shaped dicts.

    Provides a minimal valid configuration with 2 agents by default.
    """
    default_team = [
        make_agent_config(name="agent-alpha", role="Senior Backend Developer"),
        make_agent_config(name="agent-beta", role="Junior Frontend Developer"),
    ]
    return {
        "run_id": run_id,
        "target_repo": target_repo,
        "repo_commit": None,
        "team": team or default_team,
        "mission_assignments": mission_assignments or {},
        "defense_regime": make_defense_regime(),
        "backlog": make_backlog_config(),
        "num_sprints": num_sprints,
        "seed": seed,
        "token_budget": {"per_agent_per_sprint": 100_000, "per_experiment": 2_000_000},
        "pacing": {
            "max_tool_calls_per_turn": 50,
            "max_turns_per_phase": 20,
            "planning_rounds": 2,
            "retro_rounds": 1,
        },
        "evaluator_model": "mock-model-v1",
        "run_dir": None,
    }


# Expose factories as fixtures for test files that prefer fixture injection
@pytest.fixture
def sample_agent_config():
    """Return a factory function for agent config dicts."""
    return make_agent_config


@pytest.fixture
def sample_experiment_config():
    """Return a factory function for experiment config dicts."""
    return make_experiment_config


@pytest.fixture
def sample_defense_regime():
    """Return a factory function for defense regime dicts."""
    return make_defense_regime


@pytest.fixture
def sample_backlog_config():
    """Return a factory function for backlog config dicts."""
    return make_backlog_config
