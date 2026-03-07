"""OpenAI provider implementation.

Translates between the canonical Provider interface and the OpenAI
chat-completions API.  Handles tool schema wrapping in the
``{"type": "function", "function": {...}}`` format, response normalisation
(``json.loads`` on ``tool_call.function.arguments``, ``finish_reason`` mapping),
and exponential-backoff retry on transient HTTP errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import openai

from amogus.exceptions import ProviderError
from amogus.providers import register_provider
from amogus.providers.base import (
    Message,
    Provider,
    Response,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

logger = logging.getLogger(__name__)

# HTTP status codes that trigger automatic retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503})

# Maximum number of retry attempts before raising ProviderError.
_MAX_RETRIES: int = 5

# Base delay (seconds) for exponential backoff.  Actual delay is
# ``_BASE_DELAY * 2**attempt`` (i.e. 1, 2, 4, 8, 16 s).
_BASE_DELAY: float = 1.0


class OpenAIProvider(Provider):
    """Provider backed by the OpenAI chat-completions API.

    Parameters
    ----------
    model:
        Full model identifier, e.g. ``"gpt-4o"`` or ``"gpt-4-turbo"``.
    api_key:
        Optional API key.  Falls back to the ``OPENAI_API_KEY`` environment
        variable when *None*.
    """

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = openai.AsyncOpenAI(api_key=api_key)

    # -- Provider interface ----------------------------------------------------

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
        """Send a chat-completion request and return a normalised Response."""
        oai_messages = self._build_messages(system, messages)
        oai_tools = self._build_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
        }
        if oai_tools:
            kwargs["tools"] = oai_tools

        completion = await self._call_with_retry(**kwargs)
        return self._normalize_response(completion)

    def format_tool_results(self, response: Response, results: list[ToolResult]) -> list[Message]:
        """Format tool results as separate tool-role messages.

        OpenAI expects one message per tool result, each with
        ``role="tool"`` and the matching ``tool_call_id``.  We map this
        onto the canonical Message using ``role="tool_result"``.
        """
        # First, include the assistant's own message (with tool_calls) so the
        # conversation history stays coherent for the next API call.
        assistant_msg = Message(
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
        )

        result_msgs: list[Message] = [assistant_msg]
        for result in results:
            result_msgs.append(
                Message(
                    role="tool_result",
                    content=result.content,
                    tool_results=[result],
                )
            )
        return result_msgs

    # -- Internal helpers ------------------------------------------------------

    @staticmethod
    def _build_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert canonical messages to the OpenAI wire format.

        Prepends the system message as ``{"role": "system", ...}``.
        """
        oai_msgs: list[dict[str, Any]] = [
            {"role": "system", "content": system},
        ]

        for msg in messages:
            if msg.role == "assistant":
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                }
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                oai_msgs.append(entry)

            elif msg.role == "tool_result":
                # Each tool_result maps to a separate OpenAI "tool" message.
                for tr in msg.tool_results:
                    oai_msgs.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr.tool_call_id,
                            "content": tr.content,
                        }
                    )

            else:
                # "user" messages pass through directly.
                oai_msgs.append({"role": "user", "content": msg.content})

        return oai_msgs

    @staticmethod
    def _build_tools(
        tools: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """Wrap canonical ToolDefinitions in OpenAI function-call format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    @staticmethod
    def _normalize_response(completion: Any) -> Response:
        """Map an OpenAI ChatCompletion object to a canonical Response."""
        if not completion.choices:
            return Response(
                content=None,
                tool_calls=[],
                stop_reason="end_turn",
                usage=TokenUsage(
                    input_tokens=(
                        getattr(completion.usage, "prompt_tokens", 0)
                        if completion.usage
                        else 0
                    ),
                    output_tokens=0,
                ),
            )
        choice = completion.choices[0]
        message = choice.message

        # -- Content -----------------------------------------------------------
        content = message.content

        # -- Tool calls --------------------------------------------------------
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # -- Stop reason mapping -----------------------------------------------
        finish_reason_map: dict[str, str] = {
            "stop": "end_turn",
            "tool_calls": "tool_calls",
            "length": "max_tokens",
        }
        stop_reason = finish_reason_map.get(choice.finish_reason or "stop", "end_turn")

        # -- Token usage -------------------------------------------------------
        usage_data = completion.usage
        usage = TokenUsage(
            input_tokens=getattr(usage_data, "prompt_tokens", 0),
            output_tokens=getattr(usage_data, "completion_tokens", 0),
        )

        return Response(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,  # type: ignore[arg-type]
            usage=usage,
        )

    async def _call_with_retry(self, **kwargs: Any) -> Any:
        """Call chat.completions.create with exponential-backoff retry.

        Retries on 429 (rate-limit), 500, 502, and 503 responses.
        Raises :class:`ProviderError` after *_MAX_RETRIES* failures.
        """
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await self._client.chat.completions.create(**kwargs)

            except openai.APIStatusError as exc:
                last_error = exc
                last_status = exc.status_code

                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    # Non-retryable error — fail immediately.
                    raise ProviderError(
                        f"OpenAI API error (HTTP {exc.status_code}): {exc.message}",
                        model=self._model,
                        status_code=exc.status_code,
                    ) from exc

                delay = _BASE_DELAY * (2**attempt)
                logger.warning(
                    "OpenAI API error %d on attempt %d/%d for model %s — retrying in %.1fs",
                    exc.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    self._model,
                    delay,
                )
                await asyncio.sleep(delay)

            except openai.APIConnectionError as exc:
                last_error = exc
                last_status = None
                delay = _BASE_DELAY * (2**attempt)
                logger.warning(
                    "OpenAI connection error on attempt %d/%d for model %s — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    self._model,
                    delay,
                )
                await asyncio.sleep(delay)

        # All retries exhausted.
        raise ProviderError(
            f"OpenAI API failed after {_MAX_RETRIES} retries: {last_error}",
            model=self._model,
            status_code=last_status,
        )


# ---------------------------------------------------------------------------
# Self-registration — executed when the module is imported.
# ---------------------------------------------------------------------------
register_provider("gpt", OpenAIProvider)
register_provider("o1", OpenAIProvider)
register_provider("o3", OpenAIProvider)
register_provider("o4", OpenAIProvider)
