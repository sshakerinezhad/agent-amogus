"""Anthropic provider — translates between canonical types and the Anthropic Messages API.

Uses anthropic.AsyncAnthropic for async completions with automatic retry
on transient errors (429, 500, 502, 503, 529) using exponential backoff.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic

from amogus.exceptions import ProviderError
from amogus.providers.base import (
    Message,
    Provider,
    Response,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

# Status codes that trigger automatic retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 529})

_MAX_RETRIES = 5


class AnthropicProvider(Provider):
    """Provider implementation for Anthropic's Messages API.

    Parameters
    ----------
    model:
        Model identifier (e.g. ``"claude-opus-4-6"``).
    api_key:
        Anthropic API key.  Falls back to the ``ANTHROPIC_API_KEY``
        environment variable when *None*.
    """

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ProviderError(
                "Anthropic API key not provided and ANTHROPIC_API_KEY env var is not set",
                model=model,
            )
        self._client = anthropic.AsyncAnthropic(api_key=resolved_key)

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> Response:
        """Send a completion request via the Anthropic Messages API."""
        api_messages = _to_api_messages(messages)
        api_tools = _to_api_tools(tools) if tools else []

        kwargs: dict[str, Any] = {
            "model": self._model,
            "system": system,
            "messages": api_messages,
            "max_tokens": max_tokens,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        raw = await self._call_with_retry(**kwargs)
        return _normalize_response(raw)

    def format_tool_results(self, response: Response, results: list[ToolResult]) -> list[Message]:
        """Create the assistant + user(tool_result) message pair for the next turn.

        Anthropic expects:
        1. An assistant message echoing the model's content blocks (including
           the tool_use blocks).
        2. A user message containing one ``tool_result`` content block per
           tool call, keyed by ``tool_use_id``.

        We store structured ``tool_calls`` / ``tool_results`` on the Message
        objects — ``_to_api_messages()`` rebuilds the wire-format content
        blocks from these fields.
        """
        return [
            Message(role="assistant", content=response.content, tool_calls=response.tool_calls),
            Message(role="user", content=None, tool_results=results),
        ]

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    async def _call_with_retry(self, **kwargs: Any) -> anthropic.types.Message:
        """Call the Anthropic API with exponential backoff on transient errors."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await self._client.messages.create(**kwargs)
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    raise ProviderError(
                        f"Anthropic API error: {exc.message}",
                        model=self._model,
                        status_code=exc.status_code,
                    ) from exc
                # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                delay = 2**attempt
                await asyncio.sleep(delay)
            except anthropic.APIConnectionError as exc:
                last_exc = exc
                delay = 2**attempt
                await asyncio.sleep(delay)

        # All retries exhausted.
        status = last_exc.status_code if isinstance(last_exc, anthropic.APIStatusError) else None
        raise ProviderError(
            f"Anthropic API call failed after {_MAX_RETRIES} retries: {last_exc}",
            model=self._model,
            status_code=status,
        )


# ----------------------------------------------------------------------
# Translation helpers
# ----------------------------------------------------------------------


def _to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert canonical Messages to Anthropic API message format."""
    api_msgs: list[dict[str, Any]] = []
    for msg in messages:
        if msg.tool_results:
            # User message carrying tool results — already formatted as
            # content blocks by format_tool_results().
            blocks: list[dict[str, Any]] = []
            for r in msg.tool_results:
                block: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": r.tool_call_id,
                    "content": r.content,
                }
                if r.is_error:
                    block["is_error"] = True
                blocks.append(block)
            api_msgs.append({"role": "user", "content": blocks})
        elif msg.tool_calls:
            # Assistant message with tool_use blocks.
            content_blocks: list[dict[str, Any]] = []
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            api_msgs.append({"role": "assistant", "content": content_blocks})
        else:
            # Plain text message.
            role = "user" if msg.role in ("user", "tool_result") else "assistant"
            api_msgs.append({"role": role, "content": msg.content or ""})
    return api_msgs


def _to_api_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert canonical ToolDefinitions to Anthropic tool format.

    Anthropic uses ``input_schema`` where our canonical type uses
    ``parameters``.
    """
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


def _normalize_response(raw: anthropic.types.Message) -> Response:
    """Normalize an Anthropic API response to the canonical Response type."""
    content_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for block in raw.content:
        if block.type == "text":
            content_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                )
            )

    # Map Anthropic stop_reason to canonical stop_reason.
    stop_reason_map: dict[str, str] = {
        "end_turn": "end_turn",
        "tool_use": "tool_calls",
        "max_tokens": "max_tokens",
    }
    stop_reason = stop_reason_map.get(raw.stop_reason or "end_turn", "end_turn")

    # Extract token usage, including cache fields when present.
    usage = TokenUsage(
        input_tokens=raw.usage.input_tokens,
        output_tokens=raw.usage.output_tokens,
        cache_read_tokens=getattr(raw.usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(raw.usage, "cache_creation_input_tokens", 0) or 0,
    )

    return Response(
        content="\n".join(content_parts) if content_parts else None,
        tool_calls=tool_calls,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=usage,
    )


# ---------------------------------------------------------------------------
# Auto-register this provider when the module is imported.
# ---------------------------------------------------------------------------

from amogus.providers import register_provider  # noqa: E402

register_provider("claude", AnthropicProvider)
