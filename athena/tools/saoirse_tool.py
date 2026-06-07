"""Saoirse workspace, exposed as Athena tools.

Saoirse (Ross's self-hosted AI workspace) ships a scoped agent API at
``/api/codex/*`` — todos, memory, documents (RAG), calendar, email — gated by a
Bearer token. This module adapts those endpoints into Athena tools so the
orchestrator can act on Ross's actual workspace (and, via the Athena bridge,
Spidéog can too).

Config comes from the environment Saoirse already sets machine-wide:
``SAOIRSE_URL`` + ``SAOIRSE_API_TOKEN``. If either is missing, ``register_saoirse``
is a no-op and Athena runs without these tools. Tools fail safe — a network or
auth problem returns ``{"ok": False, "error": ...}`` rather than raising.

No third-party deps: HTTP is done with the standard library (urllib), keeping
the Athena core dependency-free.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from athena.tools.base import Tool, ToolRegistry

_TIMEOUT = 20  # seconds


def _config() -> tuple[str, str] | None:
    base = os.environ.get("SAOIRSE_URL", "").strip().rstrip("/")
    token = os.environ.get("SAOIRSE_API_TOKEN", "").strip()
    if not base or not token:
        return None
    return base, token


def _request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a scoped Saoirse ``/api/codex/*`` endpoint. JSON-serialisable result."""
    cfg = _config()
    if cfg is None:
        return {"ok": False, "error": "SAOIRSE_URL / SAOIRSE_API_TOKEN not set"}
    base, token = cfg
    if not path.startswith("/api/codex/"):
        return {"ok": False, "error": "only /api/codex/* endpoints are allowed"}

    url = base + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw}
            return {"ok": True, "status": resp.status, "data": payload}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        return {"ok": False, "error": f"HTTP {exc.code}: {detail or exc.reason}"}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "error": f"Saoirse unreachable: {exc}"}


class SaoirseCapabilitiesTool(Tool):
    name = "saoirse_capabilities"
    description = (
        "List which Saoirse workspace tools (todos, email, memory, calendar, "
        "documents, cookbook) the current token can use, and the actions each "
        "supports. Call this first to discover what is available."
    )
    input_schema = {"type": "object", "properties": {}}

    def run(self, **_: Any) -> dict[str, Any]:
        return _request("GET", "/api/codex/capabilities")


class SaoirseTodosTool(Tool):
    name = "saoirse_todos"
    description = (
        "Read or update Ross's Saoirse to-do list. action='list' returns todos "
        "(optionally filtered by label); action='add' creates one from 'title'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add"], "default": "list"},
            "title": {"type": "string", "description": "Todo text (for action=add)."},
            "label": {"type": "string", "description": "Filter by label (for list)."},
            "archived": {"type": "boolean", "default": False},
        },
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        action = (kwargs.get("action") or "list").lower()
        if action == "add":
            title = (kwargs.get("title") or "").strip()
            if not title:
                return {"ok": False, "error": "add requires a non-empty title"}
            return _request("POST", "/api/codex/todos",
                            body={"action": "add", "title": title})
        return _request("GET", "/api/codex/todos",
                        params={"archived": kwargs.get("archived", False),
                                "label": kwargs.get("label")})


class SaoirseMemoryTool(Tool):
    name = "saoirse_memory"
    description = (
        "Read or write Saoirse's long-term semantic memory. action='list' returns "
        "stored memories; action='add' saves 'text' (optionally a 'category'). Use "
        "to recall facts about Ross or persist something for later."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add"], "default": "list"},
            "text": {"type": "string", "description": "Memory text (for action=add)."},
            "category": {"type": "string", "default": "fact"},
        },
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        action = (kwargs.get("action") or "list").lower()
        if action == "add":
            text = (kwargs.get("text") or "").strip()
            if not text:
                return {"ok": False, "error": "add requires non-empty text"}
            return _request("POST", "/api/codex/memory",
                            body={"text": text,
                                  "category": kwargs.get("category", "fact")})
        return _request("GET", "/api/codex/memory")


class SaoirseDocumentsTool(Tool):
    name = "saoirse_documents"
    description = (
        "Search Ross's Saoirse document library (his knowledge base / RAG corpus). "
        "Returns matching documents; pass 'search' to query by topic."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Search query."},
            "limit": {"type": "integer", "default": 20},
        },
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return _request("GET", "/api/codex/documents",
                        params={"search": kwargs.get("search"),
                                "limit": kwargs.get("limit", 20)})


class SaoirseCalendarTool(Tool):
    name = "saoirse_calendar"
    description = (
        "List events from Ross's Saoirse calendar between 'start' and 'end' "
        "(ISO dates/datetimes, e.g. 2026-06-08). Use to check his schedule."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "start": {"type": "string", "description": "ISO start, e.g. 2026-06-08."},
            "end": {"type": "string", "description": "ISO end, e.g. 2026-06-15."},
        },
        "required": ["start", "end"],
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return _request("GET", "/api/codex/calendar/events",
                        params={"start": kwargs.get("start"),
                                "end": kwargs.get("end")})


class SaoirseEmailTool(Tool):
    name = "saoirse_email"
    description = (
        "List recent emails from Ross's Saoirse mailbox (read-only). Sending is "
        "intentionally not exposed to the orchestrator."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "folder": {"type": "string", "default": "INBOX"},
            "limit": {"type": "integer", "default": 10},
        },
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return _request("GET", "/api/codex/emails",
                        params={"folder": kwargs.get("folder", "INBOX"),
                                "limit": kwargs.get("limit", 10)})


def register_saoirse(registry: ToolRegistry) -> bool:
    """Register the Saoirse tools if SAOIRSE_URL + SAOIRSE_API_TOKEN are set."""
    if _config() is None:
        return False
    for tool in (
        SaoirseCapabilitiesTool(),
        SaoirseTodosTool(),
        SaoirseMemoryTool(),
        SaoirseDocumentsTool(),
        SaoirseCalendarTool(),
        SaoirseEmailTool(),
    ):
        try:
            registry.register(tool)
        except ValueError:
            pass  # already registered — stay alive
    return True
