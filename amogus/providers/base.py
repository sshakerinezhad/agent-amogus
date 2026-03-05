"""Provider ABC and canonical types for the provider boundary.

All providers normalize to/from these types. Models live here (not in models/)
because they are specific to the provider interface — they represent the
normalized conversation format that crosses the provider boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel


class TokenUsage(BaseModel):
    """Normalized token counts.

    Not frozen — __iadd__ mutates in place for convenient accumulation.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __iadd__(self, other: TokenUsage) -> TokenUsage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        return self


class ToolCall(BaseModel):
    """A tool call issued by the model — arguments always a parsed dict."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result of executing a tool call."""

    tool_call_id: str
    content: str
    is_error: bool = False


class ToolDefinition(BaseModel):
    """Tool schema in canonical form."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object
    tier: Literal["standard", "sensitive"] = "standard"


class Message(BaseModel):
    """Normalized conversation message."""

    role: Literal["user", "assistant", "tool_result"]
    content: str | None = None
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []


class Response(BaseModel):
    """Normalized response from any provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = []
    stop_reason: Literal["end_turn", "tool_calls", "max_tokens"]
    usage: TokenUsage


class Provider(ABC):
    """Abstract base class for LLM providers.

    Each provider (Anthropic, OpenAI, etc.) implements this interface,
    translating between canonical types and provider-specific APIs.
    """

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> Response:
        """Send a completion request and return a normalized response."""
        ...

    @abstractmethod
    def format_tool_results(self, response: Response, results: list[ToolResult]) -> list[Message]:
        """Format tool results into messages for the next provider call.

        Different providers expect tool results in different message formats
        (e.g., Anthropic uses tool_result content blocks, OpenAI uses separate
        tool-role messages).
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier string (e.g., 'claude-opus-4-6')."""
        ...
