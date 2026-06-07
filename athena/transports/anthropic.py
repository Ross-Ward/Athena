"""Anthropic transport — Athena's primary reasoning backend.

Adapts the Anthropic Messages API (tool use) to ``ModelTransport``. The SDK is
imported lazily so Athena installs and runs offline without `anthropic` present.
"""
from __future__ import annotations

import os
from typing import Any

from .base import AssistantTurn, Message, ModelTransport, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicTransport(ModelTransport):
    name = "anthropic"

    def __init__(self, model: str | None = None, max_tokens: int = 4096) -> None:
        self.model = model or os.getenv("ATHENA_ANTHROPIC_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._client: Any = None

    @property
    def available(self) -> bool:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> AssistantTurn:
        client = self._get_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=tools,  # already Anthropic-shaped: name/description/input_schema
            messages=_to_anthropic(messages),
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        return AssistantTurn(text="\n".join(text_parts), tool_calls=calls, raw=resp)


def _to_anthropic(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate neutral history → Anthropic message blocks."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.text})
        elif m.role == "assistant":
            content: list[dict[str, Any]] = []
            if m.text:
                content.append({"type": "text", "text": m.text})
            for c in m.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": c.id,
                        "name": c.name,
                        "input": c.arguments,
                    }
                )
            out.append({"role": "assistant", "content": content})
        elif m.role == "tool":
            content = [
                {
                    "type": "tool_result",
                    "tool_use_id": r.id,
                    "content": r.content,
                }
                for r in m.tool_results
            ]
            out.append({"role": "user", "content": content})
    return out
