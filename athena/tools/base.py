"""Tool abstraction + registry — how Athena delegates work.

A ``Tool`` is a named capability with an input schema and a ``run``. Sub-agents
(like Sionnach) are exposed as tools so the orchestrator delegates "figure out
what's left to ship" instead of reasoning it out itself.

Design patterns
---------------
* **Command**: each ``Tool`` is an executable unit with a declared interface.
* **Registry**: ``ToolRegistry`` collects tools and resolves calls by name.
* **Adapter**: concrete tools adapt an external surface (a CLI, a sub-agent's
  Python API) to the uniform ``run(**kwargs) -> dict``.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from athena.transports.base import ToolCall, ToolResult


class Tool(ABC):
    """One delegatable capability."""

    #: unique tool name the model calls
    name: str = "tool"
    #: one or more lines; first line is used in compact listings
    description: str = ""
    #: JSON Schema for the tool's arguments (Anthropic ``input_schema`` shape)
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    @abstractmethod
    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool. Return a JSON-serialisable dict. Should not raise
        for ordinary input problems — return ``{"ok": False, "error": ...}`` so
        the tool-use loop stays alive."""
        raise NotImplementedError

    def spec(self) -> dict[str, Any]:
        """Anthropic-style tool spec (also adapted by other transports)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """Holds the tools available to an orchestrator and runs calls by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]

    def execute(self, call: ToolCall) -> ToolResult:
        """Run a model-issued tool call, always returning a ToolResult."""
        tool = self._tools.get(call.name)
        if tool is None:
            payload: dict[str, Any] = {
                "ok": False,
                "error": f"unknown tool: {call.name}",
            }
        else:
            try:
                payload = tool.run(**call.arguments)
            except TypeError as exc:  # bad/missing arguments
                payload = {"ok": False, "error": f"bad arguments: {exc}"}
            except Exception as exc:  # tool blew up — keep the loop alive
                payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return ToolResult(
            id=call.id,
            name=call.name,
            content=json.dumps(payload, default=str),
        )
