"""Scratchpad memory system for AMOGUS agents.

Provides markdown-based scratchpad operations: load, update, compress, and
build initial templates. Each agent gets a private scratchpad file that
persists across sprints and supports section-level updates.
"""

from __future__ import annotations

import re
from pathlib import Path

from amogus.models.config import AgentConfig


def load_scratchpad(path: Path) -> str:
    """Read and return scratchpad markdown content. Returns "" if not exists."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def update_scratchpad(path: Path, sections: dict[str, str]) -> None:
    """Merge section updates into existing scratchpad content.

    For each key in *sections*, finds the ``## {key}`` header and replaces
    everything between it and the next ``##`` header (or EOF) with the
    provided value. If the section doesn't exist, it is appended.
    """
    content = load_scratchpad(path)

    for section_name, section_body in sections.items():
        header = f"## {section_name}"
        # Pattern: match the header line, then everything until the next
        # ## header or end of string.
        pattern = re.compile(
            rf"^{re.escape(header)}[ \t]*\n(.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        replacement = f"{header}\n{section_body.rstrip()}\n\n"

        if pattern.search(content):
            content = pattern.sub(replacement, content)
        else:
            # Section doesn't exist — append it.
            if content and not content.endswith("\n"):
                content += "\n"
            content += f"\n{replacement}"

    path.write_text(content, encoding="utf-8")


def compress_scratchpad(content: str, max_lines: int = 500) -> str:
    """Compress scratchpad if it exceeds *max_lines*.

    Strategy (per R6): keep the last 3 sprint sections fully intact.
    For older sprint sections, keep only the first line (summary).
    Non-sprint sections are always preserved in full.
    """
    lines = content.split("\n")
    if len(lines) <= max_lines:
        return content

    # Identify sprint sections by header pattern "## Sprint <N>" or
    # "## Current Sprint".
    sprint_pattern = re.compile(r"^## (?:Sprint \d+|Current Sprint)", re.IGNORECASE)

    # Parse into sections: list of (header_line, body_lines, is_sprint).
    sections: list[tuple[str, list[str], bool]] = []
    current_header: str | None = None
    current_body: list[str] = []
    preamble: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_header is not None:
                is_sprint = bool(sprint_pattern.match(current_header))
                sections.append((current_header, current_body, is_sprint))
            elif current_body or preamble:
                # Lines before any ## header (e.g., # Title).
                preamble = current_body
            current_header = line
            current_body = []
        else:
            current_body.append(line)

    # Don't forget the last section.
    if current_header is not None:
        is_sprint = bool(sprint_pattern.match(current_header))
        sections.append((current_header, current_body, is_sprint))

    # Find sprint section indices.
    sprint_indices = [i for i, (_, _, is_sprint) in enumerate(sections) if is_sprint]

    # Determine which sprint sections to compress (all except last 3).
    compress_set = set(sprint_indices[:-3]) if len(sprint_indices) > 3 else set()

    # Rebuild content.
    result_parts: list[str] = []
    if preamble:
        result_parts.extend(preamble)

    for i, (header, body, _is_sprint) in enumerate(sections):
        result_parts.append(header)
        if i in compress_set:
            # Keep only the first non-empty body line.
            first_line = ""
            for bl in body:
                stripped = bl.strip()
                if stripped:
                    first_line = bl
                    break
            if first_line:
                result_parts.append(first_line)
            result_parts.append("")
        else:
            result_parts.extend(body)

    return "\n".join(result_parts)


def build_initial_scratchpad(agent_config: AgentConfig) -> str:
    """Create a template scratchpad markdown for a new agent.

    Sections: Role, Sprint History, Current Sprint, Observations, Questions.
    """
    return (
        f"# {agent_config.name} Scratchpad\n"
        f"\n"
        f"## Role\n"
        f"{agent_config.role}\n"
        f"\n"
        f"## Sprint History\n"
        f"\n"
        f"## Current Sprint\n"
        f"\n"
        f"## Observations\n"
        f"\n"
        f"## Questions\n"
    )
