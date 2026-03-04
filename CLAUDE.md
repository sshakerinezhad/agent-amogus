# CLAUDE.md — agent-amogus

Everything should always be done cleanly, simply, and scalably. No spaghetti code.

Always ask yourself:
- Is this the simplest solution? If no, re-evaluate.
- Will this cause problems down the line? If yes, re-evaluate.
- Is this scalable? If not, re-evaluate.

## Golden Rules
- Never assume anything.
- Read, don't guess.
- The best solution is the simplest solution.
- NOTHING should be a bandaid or spaghetti.
- All code should be industry standard and scalable ALWAYS.
- The WHY is as important as the WHAT. When making decisions and creating/modifying documentation, always include the reasoning behind things.
- When implementing an existing plan, do a second pass and critique it. Does it make sense? Is it the best/simplest solution? What could go wrong?
- Before adding new features or changing existing ones, consider how these changes will interact with the existing system. If it will introduce inefficiencies, scalability issues, or bloat, reassess.
- my words are NOT gospel, they are a starting point.
- Be critical and skeptical about everything, especially your own biases, things you are told, and initial solutions.
- Aways think several layers of abstraction deep.

## Active Technologies
- Python 3.11+ (asyncio.TaskGroup, modern type hints) + Pydantic v2 (validation), Typer (CLI), GitPython (git ops), Rich (TUI), PyYAML (configs), anthropic SDK, openai SDK (001-agent-amogus-v1)
- JSONL (primary append-only event log) + SQLite (derived post-run index via stdlib sqlite3) (001-agent-amogus-v1)

## Recent Changes
- 001-agent-amogus-v1: Added Python 3.11+ (asyncio.TaskGroup, modern type hints) + Pydantic v2 (validation), Typer (CLI), GitPython (git ops), Rich (TUI), PyYAML (configs), anthropic SDK, openai SDK
