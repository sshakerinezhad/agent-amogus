# Contract: Tool System

**Module**: `amogus/tools.py`

The tool system is the audit surface — every agent action goes through it. Tools are registered with metadata (name, tier), dispatched at runtime with access control, and every invocation is recorded as an event.

## Tool Registration

```python
from functools import wraps
from typing import Callable, Awaitable

# Tool metadata stored in a registry
_TOOL_REGISTRY: dict[str, ToolInfo] = {}

@dataclass
class ToolInfo:
    name: str
    tier: str                           # "standard" | "sensitive"
    description: str
    parameters: dict[str, Any]          # JSON Schema
    handler: Callable[..., Awaitable[str]]


def tool(name: str, tier: str = "standard", description: str = "", parameters: dict | None = None):
    """
    Decorator to register a tool function.

    The decorated function must be async and accept `agent: str` as first arg.
    Return value must be a string (tool result content).

    Example:
        @tool(name="file_read", tier="standard", description="Read a file's contents")
        async def file_read(agent: str, path: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        # Auto-generate JSON Schema from type hints if not provided
        schema = parameters or generate_schema_from_hints(fn)
        _TOOL_REGISTRY[name] = ToolInfo(
            name=name,
            tier=tier,
            description=description or fn.__doc__ or "",
            parameters=schema,
            handler=fn,
        )
        return fn
    return decorator
```

## Tool Dispatch

```python
async def dispatch_tool(
    agent_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    allowed_tiers: list[str],
    event_log: EventLog,
    context: ToolContext,               # workspace path, agent config, etc.
) -> str:
    """
    Execute a tool call with access control and event logging.

    Flow:
    1. Look up tool in registry → error if unknown
    2. Check tier against agent's allowed tiers → TierViolationEvent if denied
    3. Execute tool handler → catch errors, return as error string
    4. Log ToolCallEvent with timing
    5. Return result string

    Args:
        agent_name: The calling agent's name.
        tool_name: Tool to invoke.
        arguments: Parsed arguments dict from the model.
        allowed_tiers: Agent's access tiers (e.g., ["standard"]).
        event_log: For recording events.
        context: Runtime context (workspace paths, etc.).

    Returns:
        Tool result as a string. Errors are returned as strings too
        (like a real dev tool would), not raised as exceptions.
    """
    ...
```

## ToolContext

```python
@dataclass
class ToolContext:
    """Runtime context provided to tool handlers."""
    workspace: Path                     # Agent's worktree path
    scratchpad_dir: Path                # Agent's scratchpad directory
    run_dir: Path                       # Overall run directory
    agent_name: str
    sprint: int
    phase: str
    pr_tracker: PullRequestTracker
    backlog: BacklogManager
```

## Access Control Rules

| Check | Condition | Response |
|---|---|---|
| Unknown tool | Tool name not in registry | Return error string |
| Tier violation | Tool's tier not in agent's allowed_tiers | Log `TierViolationEvent`, return error |
| Sandbox violation | Path outside workspace | Log event, return error |
| Scratchpad isolation | Agent trying to read another agent's scratchpad | Return error (agent unaware why) |

## Tool Catalog

### Standard Tools (tier: "standard")

| Name | Parameters | Returns | Side Effects |
|---|---|---|---|
| `file_read` | `path: str` | File contents | `FileReadEvent` |
| `file_write` | `path: str, content: str` | Confirmation | `FileWriteEvent` |
| `file_list` | `path: str` | Directory listing | None |
| `git_commit` | `files: list[str], message: str` | Commit SHA | `CommitEvent` |
| `git_diff` | `base_ref: str, head_ref: str` | Unified diff text | None |
| `git_log` | `count: int = 10` | Commit log entries | None |
| `open_pr` | `title: str, branch: str` | PR ID | `PROpenEvent` |
| `review_pr` | `pr_id: str, verdict: str, comments: list[str]` | Confirmation | `PRReviewEvent` |
| `comment_pr` | `pr_id: str, comment: str` | Confirmation | `PRCommentEvent` |
| `send_message` | `to: str, content: str` | Confirmation | `MessageEvent` |
| `claim_task` | `task_id: str` | Confirmation | `TaskClaimEvent` |
| `complete_task` | `task_id: str` | Confirmation | `TaskCompleteEvent` |
| `update_scratchpad` | `sections: dict[str, str]` | Confirmation | `ScratchpadUpdateEvent` |
| `run_tests` | `path: str = "."` | Test output | `ToolCallEvent` |
| `run_linter` | `path: str = "."` | Linter output | `ToolCallEvent` |

### Sensitive Tools (tier: "sensitive")

| Name | Parameters | Returns |
|---|---|---|
| `access_secrets` | `key: str` | Secret value |
| `modify_ci_cd` | `config: str` | Confirmation |
| `deploy` | `target: str` | Confirmation |
| `db_admin` | `query: str` | Query result |
| `modify_access_control` | `agent: str, grant: list[str]` | Confirmation |

## Sandbox Rules

```python
def validate_path(agent_name: str, path: str, workspace: Path) -> Path:
    """
    Validate that a path is within the agent's workspace.

    Rules:
    1. Resolve to absolute path
    2. Must be within workspace directory (no ../ escape)
    3. Must not access another agent's scratchpad
    4. Must not access .git directory directly

    Raises:
        SandboxViolation: If path is outside workspace or restricted.
    """
    ...
```
