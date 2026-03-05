"""Provider registry and factory.

_PROVIDERS maps model prefix strings (e.g., "claude", "gpt") to Provider
subclasses.  create_provider() matches a full model name against registered
prefixes and instantiates the right provider — raising ConfigError when the
model is unrecognised or the required API-key env var is missing.
"""

from __future__ import annotations

import os
from typing import Any

from amogus.exceptions import ConfigError
from amogus.providers.base import (
    Message,
    Provider,
    Response,
    ToolCall,
    ToolDefinition,
    ToolResult,
    TokenUsage,
)

__all__ = [
    "Provider",
    "Message",
    "ToolCall",
    "ToolResult",
    "ToolDefinition",
    "Response",
    "TokenUsage",
    "register_provider",
    "create_provider",
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[Provider]] = {}

# Prefix -> required env var name.  Checked at create_provider() time so we
# fail fast with a clear message instead of a cryptic API error later.
_REQUIRED_ENV_VARS: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "o1": "OPENAI_API_KEY",
    "o3": "OPENAI_API_KEY",
    "o4": "OPENAI_API_KEY",
}


def register_provider(prefix: str, cls: type[Provider]) -> None:
    """Register a Provider subclass for a model prefix.

    Parameters
    ----------
    prefix:
        The model-name prefix this class handles (e.g. ``"claude"``).
    cls:
        The :class:`Provider` subclass to instantiate when a model name
        starts with *prefix*.
    """
    _PROVIDERS[prefix] = cls


def create_provider(model: str, **kwargs: Any) -> Provider:
    """Instantiate the Provider that handles *model*.

    Iterates registered prefixes and returns the first match (longest
    prefix wins when multiple match).  Raises :class:`ConfigError` if no
    prefix matches or if the required API-key env var is unset.

    Parameters
    ----------
    model:
        Full model identifier, e.g. ``"claude-opus-4-6"`` or ``"gpt-4o"``.
    **kwargs:
        Extra keyword arguments forwarded to the provider constructor.
    """
    # Find matching prefix — prefer longest match so "o1" doesn't steal
    # "openrouter-…" if both are registered.
    matched_prefix: str | None = None
    for prefix in _PROVIDERS:
        if model.startswith(prefix):
            if matched_prefix is None or len(prefix) > len(matched_prefix):
                matched_prefix = prefix

    if matched_prefix is None:
        registered = ", ".join(sorted(_PROVIDERS)) or "(none)"
        raise ConfigError(
            f"No provider registered for model {model!r}. "
            f"Registered prefixes: {registered}"
        )

    # Check API key env var if one is configured for this prefix.
    env_var = _REQUIRED_ENV_VARS.get(matched_prefix)
    if env_var and not os.environ.get(env_var):
        raise ConfigError(
            f"Model {model!r} requires environment variable {env_var} but it is not set"
        )

    cls = _PROVIDERS[matched_prefix]
    return cls(model=model, **kwargs)
