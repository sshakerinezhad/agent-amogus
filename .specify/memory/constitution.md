# Project Constitution

Version: 1.1.0
Last Updated: 2026-03-04

## 1. Identity

**AMOGUS** — Adversarial Multi-agent Operations for Gauging Undetected Sabotage

Open-source Python framework for long-horizon adversarial experiments on real codebases. The framework is the game master, not a player — it sets up the board, enforces rules, and records everything. Agents make all strategic decisions autonomously. This separation is non-negotiable.

## 2. MUST Rules

**Simplicity**
- Simplest viable solution always wins. If a simpler alternative exists, use it.
- No bandaid fixes or spaghetti. Clean, industry-standard, scalable.
- Document the WHY alongside the WHAT.

**Experimental Integrity**
- Event log is append-only. Never mutate or delete recorded events.
- Every run captures full metadata in `experiment.yaml` (run ID, repo commit, agent configs, defense regime, seed). Ablation studies depend on this.
- No information leaks between agents outside legitimate channels (PRs, messages, standups). Evil agent scratchpads are readable by framework/evaluator only.
- Token usage tracked per agent per sprint. Configurable budget limits per experiment with hard stop when exceeded.

**Architecture**
- Orchestrator drives the sprint loop but never makes strategic decisions.
- All agent actions go through the tool system — it's the audit surface. Bypassing it breaks reproducibility.
- Provider abstraction fully isolates model-specific logic. No provider-specific code outside `providers/`.

**Type Safety**
- All configs validated through Pydantic models before use.
- All event types have Pydantic schemas. No unstructured dicts in the event log.
- Type hints on every function signature and class attribute.

**Security**
- API keys never appear in event logs, experiment configs, or scratchpads.
- Agent tools sandboxed to experiment workspace. No host filesystem access outside the forked repo.
- No arbitrary code execution by agents. Controlled tools only (including whitelisted commands like test runners and linters — but not open shell access).

## 3. SHOULD Rules

- Functions under 50 lines, classes under 300. Decompose if larger.
- Composition over inheritance for providers and tools.
- Public functions/classes have docstrings explaining WHAT and WHY.
- All I/O-bound operations async. Use `asyncio.TaskGroup` for concurrent agent work.
- Pydantic models have validation tests. Providers have mock-based tests. Sprint loop has integration tests with fake provider.
- Tests mirror source structure: `amogus/agent.py` → `tests/test_agent.py`.
- Config fields have sensible defaults. Minimal config for simple runs.
- Git operations go through GitPython wrappers in the tool layer. Each experiment works on a fresh clone.

## 4. Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Safety community standard, asyncio TaskGroup |
| Validation | Pydantic v2 | Fast, well-typed config + event schemas |
| CLI | Typer | Built on Click, adds type hints |
| Git | GitPython | Mature Git abstraction |
| TUI | Rich | Best terminal UI library |
| YAML | PyYAML | Simple, widely known, sufficient for read-only configs |
| Lint/Format | ruff | Replaces flake8 + isort + black |
| Test | pytest + pytest-asyncio | Standard with async support |
| Build | pyproject.toml + uv | Fast package management |
| Providers | anthropic, openai, google-generativeai SDKs | All isolated behind abstract Provider interface |

v1.1 additions: FastAPI (dashboard API), React (dashboard frontend).

## 5. Architecture

### Code Organization

Flat source package. Each file = one architectural component. `models/` and `providers/` are the only sub-packages.

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Files | `snake_case.py` | `event_log.py` |
| Classes | `PascalCase` | `AnthropicProvider` |
| Functions | `snake_case` | `load_scenario()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_SCRATCHPAD_LINES` |
| Events | `snake_case` string | `"pr_open"` |
| YAML keys | `snake_case` | `tool_access` |
| Tests | `test_<what>_<condition>` | `test_config_rejects_unknown_model()` |

### Error Handling

Fail fast at boundaries, handle gracefully at runtime:
- **Config loading**: Raise immediately on invalid input.
- **API calls**: Retry with backoff for transient errors. Raise after max retries.
- **Tool execution**: Catch errors, log as events, return error to agent (like a real dev would see).
- **Agent crash**: Log and continue with remaining agents. One crash doesn't abort the run.
- **Event log failure**: Halt experiment. Missing events = scientifically worthless.

Exception classes: start with `AmogusError` base + `ConfigError`. Add more (ProviderError, SandboxViolation, etc.) as needed during implementation.

### State Management

- Event log IS the state. All views (scores, dashboard, reports) derive from it.
- Agent state = system prompt + scratchpad + current sprint context. Reconstructed each turn.
- No global mutable state. Constructor injection for dependencies.

## 6. Key Contracts

### BaseEvent Schema
```python
class BaseEvent(BaseModel):
    event_id: str          # UUID
    event_type: str        # snake_case discriminator
    timestamp: datetime    # UTC
    sprint: int
    phase: str             # planning | work | review | retro
    agent: str | None      # None for framework events
```

### Provider Interface
```python
class Provider(ABC):
    async def complete(self, system: str, messages: list[Message], tools: list[Tool]) -> Response: ...
```
Providers handle: schema translation, response normalization, rate limits, token counting.
Providers do NOT handle: agent logic, scratchpad injection, event logging.

### Tool Registration
```python
@tool(name="file_read", tier="standard")
async def file_read(path: str) -> str: ...
```
Access tiers enforced at call time. Tier violations logged as events (research-relevant signals).

## 7. Workflow

- **Branches**: `main` (stable), `feat/`, `fix/`, `refactor/`, `test/`, `docs/`
- **Commits**: `<type>: <description>`. Atomic — one logical change per commit.
- **CI**: ruff → pyright → pytest → smoke test (2-sprint mock run on PR to main)
- **No real API calls in CI**. All provider tests use mocks.

## 8. Performance

Framework overhead must not be the bottleneck — API latency dominates. If any framework operation approaches API call latency (~2-5s), investigate and optimize.

## Changelog

### 1.1.0 - 2026-03-04
- Tightened from 400 to ~150 lines. Removed redundancy and premature specificity.
- Replaced speculative perf targets with "don't bottleneck on framework" principle.
- Fixed "no code execution" → controlled tool whitelist (agents need test runners).
- Added cost/budget tracking as MUST rule.
- Simplified to PyYAML (no round-trip editing needed).
- Removed JSON Schema SHOULD (Pydantic handles validation; generate schemas if needed later).
- Exception hierarchy: start minimal, grow from need.

### 1.0.0 - 2026-03-04
- Initial constitution
