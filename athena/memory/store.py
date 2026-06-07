"""Session memory — lightweight, dependency-free persistence.

A ``SessionStore`` appends finished runs to ``~/.athena/sessions.jsonl`` so Athena
keeps a durable, greppable history without pulling in a database. Behind a small
interface (Repository pattern) so a richer backend (SQLite, ChromaDB) can drop in
later without touching the orchestrator.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from athena.core.session import Session
from athena.transports.base import Message


class SessionStore(ABC):
    @abstractmethod
    def save(self, session: Session, summary: str) -> None: ...


class JsonlSessionStore(SessionStore):
    """Append-only JSON Lines store under a config dir (default ~/.athena)."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.home() / ".athena"
        self.path = self.root / "sessions.jsonl"

    def save(self, session: Session, summary: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        record = {
            "id": session.id,
            "summary": summary,
            "messages": [_msg_to_dict(m) for m in session.messages],
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


class NullSessionStore(SessionStore):
    """Persists nothing — used when ``--no-save`` or in tests."""

    def save(self, session: Session, summary: str) -> None:  # noqa: D401
        return None


def _msg_to_dict(m: Message) -> dict[str, Any]:
    return {
        "role": m.role,
        "text": m.text,
        "tool_calls": [
            {"id": c.id, "name": c.name, "arguments": c.arguments}
            for c in m.tool_calls
        ],
        "tool_results": [
            {"id": r.id, "name": r.name, "content": r.content}
            for r in m.tool_results
        ],
    }
