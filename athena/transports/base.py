"""Transport abstraction — the seam between Athena's agent loop and a backend.

A *transport* turns the running conversation (+ the available tool specs) into a
single assistant turn: either free text, or one-or-more tool calls to execute.
The orchestrator never imports a vendor SDK directly; it only speaks this
interface, so swapping Anthropic ↔ an OpenAI-compatible endpoint ↔ the offline
deterministic engine is a one-line factory change.

Design patterns
---------------
* **Strategy / Adapter**: ``ModelTransport`` is the strategy; each concrete
  backend adapts a vendor API (or the offline rules) to it.
* **Value objects**: ``Message`` / ``ToolCall`` / ``ToolResult`` / ``AssistantTurn``
  are transport-neutral so history is portable across backends.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolCall:
    """A model's request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    """The outcome of a tool call, fed back to the model on the next turn."""

    id: str          # matches the originating ToolCall.id
    name: str
    content: str     # JSON or text the model will read


@dataclass(slots=True)
class Message:
    """One turn of conversation, transport-neutral.

    ``role`` is "user" | "assistant" | "tool". An assistant turn may carry
    ``tool_calls``; a tool turn carries ``tool_results``.
    """

    role: str
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass(slots=True)
class AssistantTurn:
    """What a transport returns: text and/or tool calls. Empty ``tool_calls``
    means the model is done and ``text`` is the final answer."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None  # vendor response, for debugging


class ModelTransport(ABC):
    """Strategy interface every backend implements."""

    #: short id, e.g. "anthropic", "openai-compat", "offline"
    name: str = "transport"

    @property
    def available(self) -> bool:
        """True if this transport can actually run (key present, SDK importable)."""
        return True

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> AssistantTurn:
        """Produce the next assistant turn given history and the tool specs.

        ``tools`` are Anthropic-style specs: ``{"name", "description",
        "input_schema"}`` — transports translate to their own format as needed.
        """
        raise NotImplementedError
