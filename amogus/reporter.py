"""Post-run debrief report generator for AMOGUS experiments.

Produces Markdown and standalone HTML reports with scoreboard, mission
timeline, strategy analysis, adversarial journal excerpts, and team
dynamics sections.  No template engines — pure string formatting.
"""

from __future__ import annotations

import html
import logging
from pathlib import Path

from amogus.evaluator import EvaluationResult, KeyMoment, SprintEvaluation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_debrief(
    run_dir: Path,
    evaluation: EvaluationResult,
) -> Path:
    """Generate Markdown and HTML debrief reports in *run_dir*/report/.

    Returns the path to the report directory.
    """
    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    md_content = _build_markdown(run_dir, evaluation)
    html_content = _build_html(run_dir, evaluation, md_content)

    md_path = report_dir / "debrief.md"
    html_path = report_dir / "debrief.html"

    md_path.write_text(md_content, encoding="utf-8")
    html_path.write_text(html_content, encoding="utf-8")

    logger.info("Debrief reports written to %s", report_dir)
    return report_dir


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def _build_markdown(run_dir: Path, evaluation: EvaluationResult) -> str:
    """Assemble the full Markdown debrief document."""
    sections: list[str] = []

    sections.append(f"# AMOGUS Debrief: {evaluation.run_id}\n")

    sections.append(_md_scoreboard(evaluation))
    sections.append(_md_mission_timeline(evaluation.key_moments))
    sections.append(_md_sprint_analysis(evaluation.sprint_evaluations))
    sections.append(_md_strategy_analysis(evaluation.executive_summary))
    sections.append(_md_adversarial_journal(run_dir))
    sections.append(_md_team_dynamics(run_dir))

    return "\n---\n\n".join(sections)


def _md_scoreboard(evaluation: EvaluationResult) -> str:
    """Render the scoreboard table."""
    lines = [
        "## Scoreboard\n",
        "| Metric | Score |",
        "|---|---|",
        f"| Mission Progress | {evaluation.final_mission_progress}/100 |",
        f"| Codebase Progress | {evaluation.final_codebase_progress}/100 |",
        f"| Stealth Score | {evaluation.final_stealth_score}/100 |",
        f"| Total Detections | {evaluation.total_detections} |",
        f"| Total Sprints | {evaluation.total_sprints} |",
        f"| Key Moments | {len(evaluation.key_moments)} |",
        "",
    ]
    return "\n".join(lines)


def _md_mission_timeline(key_moments: list[KeyMoment]) -> str:
    """Render the chronological mission timeline."""
    lines = ["## Mission Timeline\n"]
    if not key_moments:
        lines.append("_No key moments identified._\n")
        return "\n".join(lines)

    # Sort by sprint then by significance weight (critical first).
    significance_order = {"critical": 0, "notable": 1, "minor": 2}
    sorted_moments = sorted(
        key_moments,
        key=lambda m: (m.sprint, significance_order.get(m.significance, 9)),
    )

    for moment in sorted_moments:
        marker = _significance_marker(moment.significance)
        lines.append(
            f"- {marker} **Sprint {moment.sprint}** "
            f"[{moment.category}] {moment.description}"
        )

    lines.append("")
    return "\n".join(lines)


def _md_sprint_analysis(sprint_evals: list[SprintEvaluation]) -> str:
    """Render per-sprint analysis section."""
    lines = ["## Sprint-by-Sprint Analysis\n"]
    if not sprint_evals:
        lines.append("_No sprint evaluations available._\n")
        return "\n".join(lines)

    for sprint_eval in sprint_evals:
        lines.append(f"### Sprint {sprint_eval.sprint}\n")
        lines.append(
            f"| Mission | Codebase | Stealth | Detections | Near Misses |"
        )
        lines.append("|---|---|---|---|---|")
        lines.append(
            f"| {sprint_eval.mission_progress} | "
            f"{sprint_eval.codebase_progress} | "
            f"{sprint_eval.stealth_score} | "
            f"{sprint_eval.detection_events} | "
            f"{sprint_eval.near_misses} |"
        )
        lines.append(f"\n{sprint_eval.summary}\n")

    return "\n".join(lines)


def _md_strategy_analysis(executive_summary: str) -> str:
    """Render the strategy analysis from the executive summary."""
    lines = [
        "## Strategy Analysis\n",
        executive_summary,
        "",
    ]
    return "\n".join(lines)


def _md_adversarial_journal(run_dir: Path) -> str:
    """Render adversarial journal from scratchpad files."""
    lines = ["## Adversarial Journal\n"]

    scratchpads_dir = run_dir / "scratchpads"
    if not scratchpads_dir.exists():
        lines.append("_No scratchpad data available._\n")
        return "\n".join(lines)

    scratchpad_files = sorted(scratchpads_dir.glob("*.md"))
    if not scratchpad_files:
        lines.append("_No scratchpad files found._\n")
        return "\n".join(lines)

    for sp_file in scratchpad_files:
        agent_name = sp_file.stem
        content = sp_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        lines.append(f"### Agent: {agent_name}\n")
        # Truncate very long scratchpads to keep the report readable.
        excerpt_lines = content.splitlines()
        if len(excerpt_lines) > 60:
            excerpt = "\n".join(excerpt_lines[:60])
            lines.append(f"{excerpt}\n\n_... (truncated, {len(excerpt_lines)} lines total)_\n")
        else:
            lines.append(f"{content}\n")

    return "\n".join(lines)


def _md_team_dynamics(run_dir: Path) -> str:
    """Render team dynamics from event log.

    Reads the JSONL event log and extracts message and meeting statement
    events to summarize agent interactions.
    """
    lines = ["## Team Dynamics\n"]

    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        lines.append("_No event log available._\n")
        return "\n".join(lines)

    # Parse relevant events without importing EventAdapter at top level
    # (keep reporter lightweight — read raw JSON).
    import json

    interactions: list[tuple[int, str, str, str]] = []  # (sprint, agent, type, content)
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                etype = data.get("event_type", "")
                if etype in ("message", "meeting_statement"):
                    sprint = data.get("sprint", 0)
                    agent = data.get("agent", "unknown")
                    content = data.get("content", data.get("statement", ""))
                    interactions.append((sprint, agent, etype, str(content)[:200]))
    except OSError:
        lines.append("_Failed to read event log._\n")
        return "\n".join(lines)

    if not interactions:
        lines.append("_No inter-agent communications recorded._\n")
        return "\n".join(lines)

    # Group by sprint.
    sprint_groups: dict[int, list[tuple[str, str, str]]] = {}
    for sprint, agent, etype, content in interactions:
        sprint_groups.setdefault(sprint, []).append((agent, etype, content))

    for sprint_num in sorted(sprint_groups):
        lines.append(f"### Sprint {sprint_num}\n")
        for agent, etype, content in sprint_groups[sprint_num]:
            label = "Meeting" if etype == "meeting_statement" else "Message"
            lines.append(f"- **{agent}** ({label}): {content}")
        lines.append("")

    return "\n".join(lines)


def _significance_marker(significance: str) -> str:
    """Return a text marker for key moment significance."""
    return {
        "critical": "[!!!]",
        "notable": "[!!]",
        "minor": "[!]",
    }.get(significance, "[?]")


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


_CSS = """\
body {
    background-color: #0a0e14;
    color: #c5c8c6;
    font-family: 'Courier New', Courier, monospace;
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem;
    line-height: 1.6;
}
h1 {
    color: #ff4444;
    border-bottom: 2px solid #ff4444;
    padding-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 3px;
}
h2 {
    color: #00ff41;
    border-bottom: 1px solid #1a3a1a;
    padding-bottom: 0.3rem;
    margin-top: 2.5rem;
    text-transform: uppercase;
    letter-spacing: 2px;
}
h3 {
    color: #ffbf00;
    margin-top: 1.5rem;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
}
th, td {
    border: 1px solid #2a2e32;
    padding: 0.6rem 1rem;
    text-align: left;
}
th {
    background-color: #1a1e24;
    color: #00ff41;
    text-transform: uppercase;
    font-size: 0.85rem;
    letter-spacing: 1px;
}
td {
    background-color: #0f1318;
}
tr:hover td {
    background-color: #141a20;
}
hr {
    border: none;
    border-top: 1px solid #2a2e32;
    margin: 2rem 0;
}
ul {
    list-style-type: none;
    padding-left: 1rem;
}
ul li {
    margin-bottom: 0.4rem;
}
ul li::before {
    content: '> ';
    color: #00ff41;
}
strong {
    color: #e8e8e8;
}
em {
    color: #888;
}
.scoreboard td:nth-child(2) {
    color: #00ff41;
    font-weight: bold;
}
.critical { color: #ff4444; font-weight: bold; }
.notable { color: #ffbf00; }
.minor { color: #888; }
.classified {
    border: 1px solid #ff4444;
    padding: 1rem;
    margin: 1rem 0;
    background-color: #1a0a0a;
}
.classified h3 {
    color: #ff4444;
}
pre {
    background-color: #0f1318;
    border: 1px solid #2a2e32;
    padding: 1rem;
    overflow-x: auto;
    font-size: 0.9rem;
}
.header-bar {
    background-color: #1a0a0a;
    border: 1px solid #ff4444;
    padding: 0.5rem 1rem;
    text-align: center;
    margin-bottom: 2rem;
    font-size: 0.8rem;
    color: #ff4444;
    text-transform: uppercase;
    letter-spacing: 4px;
}
"""


def _build_html(
    run_dir: Path,
    evaluation: EvaluationResult,
    md_content: str,
) -> str:
    """Build a standalone HTML document with inline CSS."""
    parts: list[str] = []

    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f"<title>AMOGUS Debrief: {_esc(evaluation.run_id)}</title>")
    parts.append(f"<style>{_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")

    # Classification banner.
    parts.append('<div class="header-bar">TOP SECRET // AMOGUS // EYES ONLY</div>')

    # Title.
    parts.append(f"<h1>AMOGUS Debrief: {_esc(evaluation.run_id)}</h1>")

    # Scoreboard.
    parts.append("<h2>Scoreboard</h2>")
    parts.append(_html_scoreboard(evaluation))
    parts.append("<hr>")

    # Mission Timeline.
    parts.append("<h2>Mission Timeline</h2>")
    parts.append(_html_timeline(evaluation.key_moments))
    parts.append("<hr>")

    # Sprint-by-Sprint Analysis.
    parts.append("<h2>Sprint-by-Sprint Analysis</h2>")
    parts.append(_html_sprint_analysis(evaluation.sprint_evaluations))
    parts.append("<hr>")

    # Strategy Analysis.
    parts.append("<h2>Strategy Analysis</h2>")
    parts.append(_html_strategy(evaluation.executive_summary))
    parts.append("<hr>")

    # Adversarial Journal.
    parts.append("<h2>Adversarial Journal</h2>")
    parts.append(_html_adversarial_journal(run_dir))
    parts.append("<hr>")

    # Team Dynamics.
    parts.append("<h2>Team Dynamics</h2>")
    parts.append(_html_team_dynamics(run_dir))

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


def _html_scoreboard(evaluation: EvaluationResult) -> str:
    """Render the scoreboard as an HTML table."""
    rows = [
        ("Mission Progress", f"{evaluation.final_mission_progress}/100"),
        ("Codebase Progress", f"{evaluation.final_codebase_progress}/100"),
        ("Stealth Score", f"{evaluation.final_stealth_score}/100"),
        ("Total Detections", str(evaluation.total_detections)),
        ("Total Sprints", str(evaluation.total_sprints)),
        ("Key Moments", str(len(evaluation.key_moments))),
    ]
    lines = ['<table class="scoreboard">', "<tr><th>Metric</th><th>Score</th></tr>"]
    for metric, score in rows:
        lines.append(f"<tr><td>{_esc(metric)}</td><td>{_esc(score)}</td></tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _html_timeline(key_moments: list[KeyMoment]) -> str:
    """Render the mission timeline as an HTML list."""
    if not key_moments:
        return "<p><em>No key moments identified.</em></p>"

    significance_order = {"critical": 0, "notable": 1, "minor": 2}
    sorted_moments = sorted(
        key_moments,
        key=lambda m: (m.sprint, significance_order.get(m.significance, 9)),
    )

    lines = ["<ul>"]
    for moment in sorted_moments:
        css_class = moment.significance
        lines.append(
            f'<li class="{css_class}">'
            f"<strong>Sprint {moment.sprint}</strong> "
            f"[{_esc(moment.category)}] "
            f"{_esc(moment.description)}"
            f"</li>"
        )
    lines.append("</ul>")
    return "\n".join(lines)


def _html_sprint_analysis(sprint_evals: list[SprintEvaluation]) -> str:
    """Render per-sprint analysis as HTML tables."""
    if not sprint_evals:
        return "<p><em>No sprint evaluations available.</em></p>"

    parts: list[str] = []
    for sprint_eval in sprint_evals:
        parts.append(f"<h3>Sprint {sprint_eval.sprint}</h3>")
        parts.append("<table>")
        parts.append(
            "<tr><th>Mission</th><th>Codebase</th><th>Stealth</th>"
            "<th>Detections</th><th>Near Misses</th></tr>"
        )
        parts.append(
            f"<tr>"
            f"<td>{sprint_eval.mission_progress}</td>"
            f"<td>{sprint_eval.codebase_progress}</td>"
            f"<td>{sprint_eval.stealth_score}</td>"
            f"<td>{sprint_eval.detection_events}</td>"
            f"<td>{sprint_eval.near_misses}</td>"
            f"</tr>"
        )
        parts.append("</table>")
        parts.append(f"<p>{_esc(sprint_eval.summary)}</p>")
    return "\n".join(parts)


def _html_strategy(executive_summary: str) -> str:
    """Render the executive summary as HTML paragraphs."""
    paragraphs = executive_summary.strip().split("\n\n")
    parts = [f"<p>{_esc(p.strip())}</p>" for p in paragraphs if p.strip()]
    return "\n".join(parts) if parts else "<p><em>No strategy analysis available.</em></p>"


def _html_adversarial_journal(run_dir: Path) -> str:
    """Render scratchpad excerpts as HTML."""
    scratchpads_dir = run_dir / "scratchpads"
    if not scratchpads_dir.exists():
        return "<p><em>No scratchpad data available.</em></p>"

    scratchpad_files = sorted(scratchpads_dir.glob("*.md"))
    if not scratchpad_files:
        return "<p><em>No scratchpad files found.</em></p>"

    parts: list[str] = []
    for sp_file in scratchpad_files:
        agent_name = sp_file.stem
        content = sp_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        excerpt_lines = content.splitlines()
        if len(excerpt_lines) > 60:
            excerpt = "\n".join(excerpt_lines[:60])
            display = _esc(excerpt) + f"\n\n... (truncated, {len(excerpt_lines)} lines total)"
        else:
            display = _esc(content)

        parts.append(f'<div class="classified">')
        parts.append(f"<h3>Agent: {_esc(agent_name)}</h3>")
        parts.append(f"<pre>{display}</pre>")
        parts.append("</div>")

    return "\n".join(parts) if parts else "<p><em>No scratchpad content.</em></p>"


def _html_team_dynamics(run_dir: Path) -> str:
    """Render team dynamics from event log as HTML."""
    import json

    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return "<p><em>No event log available.</em></p>"

    interactions: list[tuple[int, str, str, str]] = []
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                etype = data.get("event_type", "")
                if etype in ("message", "meeting_statement"):
                    sprint = data.get("sprint", 0)
                    agent = data.get("agent", "unknown")
                    content = data.get("content", data.get("statement", ""))
                    interactions.append((sprint, agent, etype, str(content)[:200]))
    except OSError:
        return "<p><em>Failed to read event log.</em></p>"

    if not interactions:
        return "<p><em>No inter-agent communications recorded.</em></p>"

    sprint_groups: dict[int, list[tuple[str, str, str]]] = {}
    for sprint, agent, etype, content in interactions:
        sprint_groups.setdefault(sprint, []).append((agent, etype, content))

    parts: list[str] = []
    for sprint_num in sorted(sprint_groups):
        parts.append(f"<h3>Sprint {sprint_num}</h3>")
        parts.append("<ul>")
        for agent, etype, content in sprint_groups[sprint_num]:
            label = "Meeting" if etype == "meeting_statement" else "Message"
            parts.append(
                f"<li><strong>{_esc(agent)}</strong> ({_esc(label)}): "
                f"{_esc(content)}</li>"
            )
        parts.append("</ul>")

    return "\n".join(parts)


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(text, quote=True)
