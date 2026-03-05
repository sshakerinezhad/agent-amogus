"""Filesystem sandbox — enforces path boundaries for agent workspace access.

Every file operation an agent performs is validated through ``validate_path``
before execution. This prevents workspace escapes, cross-agent scratchpad
reads, and direct ``.git`` manipulation.
"""

from __future__ import annotations

from pathlib import Path

from amogus.exceptions import SandboxViolation


def validate_path(agent_name: str, path: str, workspace: Path) -> Path:
    """Resolve *path* relative to *workspace* and enforce sandbox rules.

    Rules
    -----
    1. Resolve to an absolute path (relative to *workspace*).
    2. The resolved path must remain within *workspace* (no ``../`` escape).
    3. Paths into ``scratchpads/`` must belong to the calling agent
       (``scratchpads/{agent_name}/…`` is OK; other names are blocked).
    4. Direct ``.git`` directory access is forbidden.

    Returns the resolved absolute :class:`~pathlib.Path` on success.

    Raises
    ------
    SandboxViolation
        If any rule is violated, with a human-readable message.
    """
    resolved_workspace = workspace.resolve()
    resolved = (workspace / path).resolve()

    # Rule 1+2: path must stay within the workspace
    try:
        resolved.relative_to(resolved_workspace)
    except ValueError as exc:
        raise SandboxViolation(f"Path escapes workspace: {path}") from exc

    # Compute relative parts for component-level checks
    rel = resolved.relative_to(resolved_workspace)
    parts = rel.parts

    # Rule 3: scratchpad isolation — block access to other agents' scratchpads
    for i, part in enumerate(parts):
        if part == "scratchpads" and i + 1 < len(parts):
            owner = parts[i + 1]
            if owner != agent_name:
                raise SandboxViolation("Cannot access another agent's scratchpad")
            break  # found the relevant scratchpads segment, no need to continue

    # Rule 4: no direct .git access
    if ".git" in parts:
        raise SandboxViolation("Direct .git access is forbidden")

    return resolved
