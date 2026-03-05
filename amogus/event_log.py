"""Append-only JSONL event log with async I/O.

EventLog provides thread-safe, async-friendly persistence for experiment
events.  All file I/O is dispatched to a thread pool via
``asyncio.to_thread`` so the event loop is never blocked.  A
``threading.Lock`` (not ``asyncio.Lock``) guards writes because the
actual I/O happens on OS threads.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from amogus.models.events import BaseEvent, Event, EventAdapter


class EventLog:
    """Append-only JSONL event log backed by a single file.

    Parameters
    ----------
    path:
        Filesystem path for the ``.jsonl`` file.  Parent directories and
        the file itself are created if they do not already exist.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

        # Ensure parent dirs and file exist (sync — called once at init).
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def append(self, event: BaseEvent) -> None:
        """Serialize *event* as a single JSON line and flush to disk."""
        line = event.model_dump_json() + "\n"
        await asyncio.to_thread(self._write_line, line)

    def _write_line(self, line: str) -> None:
        """Thread-safe, synchronous file append (runs in worker thread)."""
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()

    # ------------------------------------------------------------------
    # Read helpers (all offloaded to threads)
    # ------------------------------------------------------------------

    async def read_all(self) -> list[Event]:
        """Parse every line in the log and return typed events."""
        return await asyncio.to_thread(self._read_all_sync)

    def _read_all_sync(self) -> list[Event]:
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [EventAdapter.validate_json(line) for line in lines if line.strip()]

    async def read_filtered(
        self,
        event_type: str | None = None,
        sprint: int | None = None,
        agent: str | None = None,
        phase: str | None = None,
    ) -> list[Event]:
        """Read all events then filter in memory by the given criteria."""
        events = await self.read_all()
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if sprint is not None:
            events = [e for e in events if e.sprint == sprint]
        if agent is not None:
            events = [e for e in events if e.agent == agent]
        if phase is not None:
            events = [e for e in events if e.phase == phase]
        return events

    async def tail(self, n: int) -> list[Event]:
        """Return the last *n* events from the log."""
        return await asyncio.to_thread(self._tail_sync, n)

    def _tail_sync(self, n: int) -> list[Event]:
        lines = self._path.read_text(encoding="utf-8").splitlines()
        # Filter out blank lines, take the last n
        non_empty = [line for line in lines if line.strip()]
        tail_lines = non_empty[-n:] if n > 0 else []
        return [EventAdapter.validate_json(line) for line in tail_lines]
