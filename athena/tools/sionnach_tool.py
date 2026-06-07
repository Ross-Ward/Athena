"""Sionnach sub-agent, exposed as Athena tools.

Athena does not reason out a project's production-readiness itself — it delegates
to Sionnach (the fox: production-readiness inspector). These two tools wrap
Sionnach's own bridge (`sionnach.integrations.athena`), so the contract lives
with Sionnach and Athena just adapts it into its registry.

Sionnach is an optional dependency: if it isn't importable, ``register_sionnach``
is a no-op and Athena simply runs without these tools.
"""
from __future__ import annotations

from typing import Any

from athena.tools.base import Tool, ToolRegistry


def _bridge() -> Any:
    """Lazy import of Sionnach's Athena bridge (preferred) or legacy hermes shim."""
    try:
        from sionnach.integrations import athena as bridge  # type: ignore
        return bridge
    except ImportError:
        from sionnach.integrations import hermes as bridge  # type: ignore
        return bridge


class SionnachScanTool(Tool):
    name = "sionnach_scan"
    description = (
        "Analyse ONE project directory and return the prioritised backlog of "
        "tasks needed to bring it to production (tests, CI, docs, secrets, deps, "
        "packaging, container, typing, observability, license). Use to triage "
        "what is left before a single project can ship."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the project root.",
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "json", "table"],
                "default": "markdown",
                "description": "Rendering of the human-readable backlog.",
            },
            "advisor": {
                "type": "boolean",
                "default": False,
                "description": "Enable optional LLM enrichment (needs a key).",
            },
        },
        "required": ["path"],
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        b = _bridge()
        fn = getattr(b, "run_scan", None) or getattr(b, "run_tool")
        return fn(
            path=kwargs["path"],
            format=kwargs.get("format", "markdown"),
            advisor=kwargs.get("advisor", False),
        )


class SionnachFleetTool(Tool):
    name = "sionnach_fleet"
    description = (
        "Scan EVERY immediate subdirectory of a folder as a separate project and "
        "rank them worst-first by how far each is from production. Use to triage "
        "a whole portfolio and decide what to fix next."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to a folder containing project subdirectories.",
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "json", "table"],
                "default": "table",
                "description": "Rendering of the ranked fleet report.",
            },
            "limit": {
                "type": "integer",
                "description": "Max projects to include (worst-first). Optional.",
            },
        },
        "required": ["path"],
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        b = _bridge()
        fn = getattr(b, "run_fleet", None)
        if fn is None:
            return {
                "ok": False,
                "error": "installed Sionnach has no fleet bridge; upgrade it.",
            }
        return fn(
            path=kwargs["path"],
            format=kwargs.get("format", "table"),
            limit=kwargs.get("limit"),
        )


def register_sionnach(registry: ToolRegistry) -> bool:
    """Register the Sionnach tools if Sionnach is importable. Returns success."""
    try:
        _bridge()
    except ImportError:
        return False
    registry.register(SionnachScanTool())
    registry.register(SionnachFleetTool())
    return True
