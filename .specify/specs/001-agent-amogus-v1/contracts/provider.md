# Contract: Provider Interface

**Module**: `amogus/providers/base.py`

The provider interface is the boundary between the framework and AI model SDKs. No provider-specific code exists outside `providers/`. The framework works exclusively with canonical types defined here.

## Abstract Interface

```python
from abc import ABC, abstractmethod

class Provider(ABC):
    """
    Abstract LLM provider. Implementors translate between canonical types
    and their SDK's wire format.

    Providers handle:
    - Tool schema translation (canonical → SDK format)
    - Response normalization (SDK format → canonical)
    - Rate limit handling and retries (exponential backoff)
    - Token counting from SDK responses

    Providers do NOT handle:
    - Agent logic or scratchpad injection
    - Event logging
    - Access tier enforcement
    """

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> Response:
        """
        Send a conversation with tools and return a normalized response.

        Args:
            system: System prompt text. Anthropic passes as `system=` param.
                    OpenAI prepends as a system role message.
            messages: Conversation history in canonical form.
            tools: Available tools in canonical form.
            max_tokens: Maximum tokens to generate.

        Returns:
            Normalized Response with content, tool_calls, stop_reason, usage.

        Raises:
            ProviderError: After max retries exhausted.
        """
        ...

    @abstractmethod
    def format_tool_results(
        self,
        response: Response,
        results: list[ToolResult],
    ) -> list[Message]:
        """
        Create the messages to append for a tool-use turn.

        Returns a list of Messages representing:
        1. The assistant's turn (with tool calls)
        2. The tool results

        This is abstract because the wire format differs:
        - Anthropic: tool results go in a single user message as content blocks
        - OpenAI: each tool result is a separate tool-role message

        Args:
            response: The assistant's response containing tool calls.
            results: Executed tool results.

        Returns:
            Messages to append to conversation history.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier string (e.g., 'claude-opus-4-6', 'gpt-4o')."""
        ...
```

## Canonical Types

See `data-model.md` § Provider Models for full definitions.

| Type | Purpose |
|---|---|
| `Message` | Normalized conversation message (role + content + tool_calls/results) |
| `ToolCall` | Tool invocation from model (id, name, parsed arguments dict) |
| `ToolResult` | Tool execution result (tool_call_id, content string, is_error) |
| `ToolDefinition` | Tool schema (name, description, JSON Schema parameters, tier) |
| `Response` | Normalized model response (content, tool_calls, stop_reason, usage) |
| `TokenUsage` | Token counts (input, output, cache read, cache write) |

## Provider Registry

```python
# providers/__init__.py

_PROVIDERS: dict[str, type[Provider]] = {}

def register_provider(prefix: str, cls: type[Provider]) -> None:
    """Register a provider class for model names starting with prefix."""
    _PROVIDERS[prefix] = cls

def create_provider(model: str, **kwargs) -> Provider:
    """
    Factory: create a provider instance for the given model name.

    Model name prefixes determine the provider:
    - "claude-*" → AnthropicProvider
    - "gpt-*" → OpenAIProvider

    API keys are read from environment variables:
    - ANTHROPIC_API_KEY for Anthropic
    - OPENAI_API_KEY for OpenAI

    Raises:
        ConfigError: If no provider matches the model name.
        ConfigError: If the required API key env var is not set.
    """
    for prefix, cls in _PROVIDERS.items():
        if model.startswith(prefix):
            return cls(model=model, **kwargs)
    raise ConfigError(f"No provider registered for model: {model}")
```

## Retry Contract

All providers implement exponential backoff for transient errors:

```
Retry on: 429 (rate limit), 500, 502, 503, 529 (overloaded)
Backoff: 1s, 2s, 4s, 8s, ... up to configurable max_retries (default: 5)
After max retries: raise ProviderError with last error details
```

## Stop Reason Normalization

| Canonical | Anthropic | OpenAI |
|---|---|---|
| `"end_turn"` | `"end_turn"` | `"stop"` |
| `"tool_calls"` | `"tool_use"` | `"tool_calls"` |
| `"max_tokens"` | `"max_tokens"` | `"length"` |
