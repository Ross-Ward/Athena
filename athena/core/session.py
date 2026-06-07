"""Session — the running conversation Athena reasons over.

A thin, append-only wrapper around the neutral ``Message`` history plus a stable
session id. Kept separate from the orchestrator so it can be persisted (see
``athena.memory``) and replayed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from athena.transports.base import Message, ToolCall, ToolResult


@dataclass(slots=True)
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[Message] = field(default_factory=list)

    def add_user(self, text: str) -> None:
        self.messages.append(Message(role="user", text=text))

    def add_assistant(self, text: str, tool_calls: list[ToolCall] | None = None) -> None:
        self.messages.append(
            Message(role="assistant", text=text, tool_calls=tool_calls or [])
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.messages.append(Message(role="tool", tool_results=results))

    @property
    def last(self) -> Message | None:
        return self.messages[-1] if self.messages else None
