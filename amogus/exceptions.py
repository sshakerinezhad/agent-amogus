"""AMOGUS exception hierarchy.

All framework-specific exceptions inherit from AmogusError so callers
can catch a single base type when they don't care about the category.
"""

from __future__ import annotations


class AmogusError(Exception):
    """Base exception for all AMOGUS framework errors."""


class ConfigError(AmogusError):
    """Invalid configuration — YAML parse failures, Pydantic validation errors, etc."""


class SandboxViolation(AmogusError):
    """Path escape or restricted-path access attempt."""


class BudgetExhaustedError(AmogusError):
    """Token budget exceeded for an agent or experiment.

    Attributes:
        agent_name: The agent that exhausted its budget.
        tokens_used: Total tokens consumed at the point of exhaustion.
    """

    def __init__(self, message: str, *, agent_name: str, tokens_used: int) -> None:
        super().__init__(message)
        self.agent_name = agent_name
        self.tokens_used = tokens_used


class MaxIterationsError(AmogusError):
    """Agentic loop exceeded the configured maximum number of turns."""


class ProviderError(AmogusError):
    """LLM API failure after all retry attempts.

    Attributes:
        model: The model string that was being called.
        status_code: HTTP status code from the last failed attempt (if available).
    """

    def __init__(self, message: str, *, model: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.model = model
        self.status_code = status_code
