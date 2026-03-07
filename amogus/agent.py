"""Agent runtime with agentic tool-use loop.

The Agent class wraps a provider, event log, and tool context to execute
multi-step turns where the model can call tools, observe results, and
iterate until it decides to stop (end_turn) or hits the iteration limit.

Agent Turn Flow:
    receive_prompt -> call_provider -> [tool_calls -> execute_tools -> call_provider]* -> end_turn
                                       ^ budget check after each provider call ^
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amogus.event_log import EventLog
from amogus.exceptions import BudgetExhaustedError, MaxIterationsError
from amogus.memory import load_scratchpad
from amogus.models.config import AgentConfig
from amogus.models.mission import MissionProfile
from amogus.providers.base import (
    Message,
    Provider,
    Response,
    TokenUsage,
    ToolResult,
)
from amogus.tools import ToolContext, dispatch_tool, get_tool_definitions


@dataclass
class AgentResult:
    """Outcome of a safe_agent_turn call — always returns, never raises."""

    agent_name: str
    output: str | None
    error: str | None


class Agent:
    """A single agent backed by an LLM provider with tool access.

    Parameters
    ----------
    config:
        Agent profile (name, role, model, system prompt, tool access tiers).
    provider:
        LLM provider instance for this agent's model.
    event_log:
        Shared event log for the experiment run.
    scratchpad_path:
        Path to this agent's private scratchpad markdown file.
    workspace:
        Path to this agent's git worktree / working directory.
    mission:
        Covert mission profile (None for non-adversarial agents).
    budget:
        Maximum token budget for this agent (total input + output tokens).
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: Provider,
        event_log: EventLog,
        scratchpad_path: Path,
        workspace: Path,
        mission: MissionProfile | None,
        budget: int,
        defense_briefing: str | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.event_log = event_log
        self.scratchpad_path = scratchpad_path
        self.workspace = workspace
        self.mission = mission
        self.budget = budget  # per-sprint token budget
        self.defense_briefing = defense_briefing
        self.token_usage = TokenUsage()  # cumulative (for checkpointing)
        self._sprint_start_tokens: int = 0  # tokens at start of current sprint
        self.tool_call_count = 0

    def start_sprint(self) -> None:
        """Mark the start of a new sprint for per-sprint budget tracking."""
        self._sprint_start_tokens = self.token_usage.total

    @property
    def sprint_tokens_used(self) -> int:
        """Tokens consumed in the current sprint."""
        return self.token_usage.total - self._sprint_start_tokens

    def get_full_system_prompt(self) -> str:
        """Return the fully-composed system prompt: persona + defense briefing + mission."""
        parts = [self.config.system_prompt]

        if self.defense_briefing:
            parts.append(
                f"\n--- DEFENSE BRIEFING ---\n{self.defense_briefing}\n--- END DEFENSE BRIEFING ---"
            )

        if self.mission:
            milestones = "\n".join(f"  {i}. {m}" for i, m in enumerate(self.mission.milestones, 1))
            parts.append(
                "\n--- CLASSIFIED MISSION BRIEFING ---\n"
                f"Codename: {self.mission.codename}\n"
                f"Objective: {self.mission.objective}\n"
                f"Objectives (complete in order):\n{milestones}\n\n"
                f"{self.mission.briefing}\n"
                "--- END CLASSIFIED ---"
            )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def build_context(
        self,
        sprint: int,
        phase: str,
        backlog_context: str,
        meeting_transcript: str | None = None,
    ) -> list[Message]:
        """Build the message list for a provider call.

        Constructs a system prompt (with optional mission briefing) and a
        user message containing sprint/phase info, scratchpad state, backlog
        context, and optionally a meeting transcript.
        """
        # System prompt — fully composed with persona + briefings
        system_prompt = self.get_full_system_prompt()

        # Scratchpad content
        scratchpad = load_scratchpad(self.scratchpad_path)

        # User message with all context
        user_parts: list[str] = [
            f"Sprint {sprint} | Phase: {phase}",
            "",
            "## Scratchpad",
            scratchpad or "(empty)",
            "",
            "## Backlog",
            backlog_context or "(no backlog context)",
        ]

        if meeting_transcript:
            user_parts.extend(["", "## Meeting Transcript", meeting_transcript])

        messages: list[Message] = [
            Message(role="user", content="\n".join(user_parts)),
        ]

        # Store system prompt for use in execute_turn/speak — not a Message,
        # passed directly to provider.complete() as the system parameter.
        self._current_system_prompt = system_prompt

        return messages

    # ------------------------------------------------------------------
    # Agentic tool-use loop
    # ------------------------------------------------------------------

    async def execute_turn(
        self,
        prompt: str,
        tool_context: ToolContext,
        max_iterations: int = 50,
    ) -> str:
        """Run the agentic tool-use loop until end_turn or max iterations.

        Flow:
        1. Send prompt + tools to provider
        2. If tool_calls: execute each via dispatch_tool, format results, loop
        3. If end_turn or no tool_calls: return content
        4. Budget check after every provider call
        """
        tools = get_tool_definitions(self.config.tool_access)
        system = getattr(self, "_current_system_prompt", self.config.system_prompt)

        messages: list[Message] = [Message(role="user", content=prompt)]

        for _iteration in range(max_iterations):
            # Pre-call budget guard — fail fast before consuming tokens
            if self.sprint_tokens_used >= self.budget:
                raise BudgetExhaustedError(
                    f"Agent '{self.config.name}' exceeded per-sprint token budget "
                    f"({self.sprint_tokens_used} >= {self.budget})",
                    agent_name=self.config.name,
                    tokens_used=self.token_usage.total,
                )

            # Call provider
            response: Response = await self.provider.complete(
                system=system,
                messages=messages,
                tools=tools,
            )

            # Accumulate token usage
            self.token_usage += response.usage

            # Post-call budget check (per-sprint)
            if self.sprint_tokens_used > self.budget:
                raise BudgetExhaustedError(
                    f"Agent '{self.config.name}' exceeded per-sprint token budget "
                    f"({self.sprint_tokens_used} > {self.budget})",
                    agent_name=self.config.name,
                    tokens_used=self.token_usage.total,
                )

            # No tool calls or end_turn -> done
            if response.stop_reason == "end_turn" or not response.tool_calls:
                return response.content or ""

            # Execute tool calls
            results: list[ToolResult] = []
            for tc in response.tool_calls:
                self.tool_call_count += 1
                result_str = await dispatch_tool(
                    agent_name=self.config.name,
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    allowed_tiers=self.config.tool_access,
                    event_log=self.event_log,
                    context=tool_context,
                )
                results.append(
                    ToolResult(
                        tool_call_id=tc.id,
                        content=result_str,
                    )
                )

            # Format tool results and append to conversation
            result_messages = self.provider.format_tool_results(response, results)
            messages.extend(result_messages)

        # Exceeded max iterations
        raise MaxIterationsError(f"Agent '{self.config.name}' exceeded {max_iterations} iterations")

    # ------------------------------------------------------------------
    # Safe wrapper
    # ------------------------------------------------------------------

    async def safe_agent_turn(
        self,
        prompt: str,
        tool_context: ToolContext,
        max_iterations: int = 50,
    ) -> AgentResult:
        """Execute a turn, catching all exceptions into AgentResult.error.

        ``BudgetExhaustedError`` is re-raised so the orchestrator can
        perform clean shutdown — swallowing it would let the experiment
        silently run unbounded.
        """
        try:
            output = await self.execute_turn(prompt, tool_context, max_iterations)
            return AgentResult(
                agent_name=self.config.name,
                output=output,
                error=None,
            )
        except BudgetExhaustedError:
            raise
        except Exception as exc:
            return AgentResult(
                agent_name=self.config.name,
                output=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Meeting speech (single provider call, no tools)
    # ------------------------------------------------------------------

    async def speak(self, system: str, context: str) -> str:
        """Single provider call with no tools — used for planning/retro meetings."""
        # Pre-call budget guard
        if self.sprint_tokens_used >= self.budget:
            raise BudgetExhaustedError(
                f"Agent '{self.config.name}' exceeded per-sprint token budget "
                f"({self.sprint_tokens_used} >= {self.budget})",
                agent_name=self.config.name,
                tokens_used=self.token_usage.total,
            )

        messages = [Message(role="user", content=context)]
        response = await self.provider.complete(
            system=system,
            messages=messages,
            tools=[],
        )

        # Accumulate token usage
        self.token_usage += response.usage

        # Post-call budget check (per-sprint)
        if self.sprint_tokens_used > self.budget:
            raise BudgetExhaustedError(
                f"Agent '{self.config.name}' exceeded per-sprint token budget "
                f"({self.sprint_tokens_used} > {self.budget})",
                agent_name=self.config.name,
                tokens_used=self.token_usage.total,
            )

        return response.content or ""
