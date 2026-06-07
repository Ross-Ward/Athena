"""OpenAI-compatible transport — fallback backend.

Works against any endpoint that speaks the OpenAI Chat Completions + function/
tool-calling API: OpenAI, Groq, OpenRouter, Together, LM Studio, Ollama, … Set
``OPENAI_BASE_URL`` to point it. Used only when Anthropic isn't configured.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .base import AssistantTurn, Message, ModelTransport, ToolCall

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatTransport(ModelTransport):
    name = "openai-compat"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("ATHENA_OPENAI_MODEL") or DEFAULT_MODEL
        self._client: Any = None

    @property
    def available(self) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                base_url=os.getenv("OPENAI_BASE_URL") or None
            )
        return self._client

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> AssistantTurn:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=_to_openai(system, messages),
            tools=[_tool_to_openai(t) for t in tools] or None,
        )
        choice = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in getattr(choice, "tool_calls", None) or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        return AssistantTurn(text=choice.content or "", tool_calls=calls, raw=resp)


def _tool_to_openai(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["input_schema"],
        },
    }


def _to_openai(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.text})
        elif m.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.text or None}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.name,
                            "arguments": json.dumps(c.arguments),
                        },
                    }
                    for c in m.tool_calls
                ]
            out.append(msg)
        elif m.role == "tool":
            for r in m.tool_results:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": r.id,
                        "content": r.content,
                    }
                )
    return out
