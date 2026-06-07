"""Offline-deterministic transport — Athena's safe default with no API key.

It is not an LLM. It is a tiny intent router that lets Athena still be *useful*
and its agent loop still be *testable* with zero credentials and zero network:

* A user message of the form ``scan <path>`` / ``fleet <dir>`` (or one that names
  a registered tool) is turned into a real tool call.
* Once a tool result is on the history, it ends the loop and surfaces the tool's
  rendered output as the final answer.
* Anything else returns a help turn listing the available tools.

This mirrors Sionnach's "offline & deterministic by default" ethos: same input →
same output, no surprises. Add a key (Anthropic / OpenAI-compat) to swap in real
reasoning over the same tools.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .base import AssistantTurn, Message, ModelTransport, ToolCall

# "scan <path>", "fleet <dir>" — the two verbs Sionnach exposes today. New tools
# can be matched generically by name below.
_VERB_RE = re.compile(r"^\s*(scan|fleet)\s+(.+?)\s*$", re.IGNORECASE)
_VERB_TO_TOOL = {"scan": "sionnach_scan", "fleet": "sionnach_fleet"}


class OfflineTransport(ModelTransport):
    name = "offline"

    def __init__(self) -> None:
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"offline-{self._counter}"

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> AssistantTurn:
        if not messages:
            return AssistantTurn(text=_help(tools))

        last = messages[-1]

        # A tool just ran → summarise and finish (no further tool calls).
        if last.role == "tool":
            return AssistantTurn(text=_summarise(last.tool_results))

        # Otherwise treat the latest user text as a directive.
        text = last.text or ""
        tool_names = {t["name"] for t in tools}

        m = _VERB_RE.match(text)
        if m:
            verb, arg = m.group(1).lower(), m.group(2).strip().strip('"')
            tool = _VERB_TO_TOOL.get(verb)
            if tool in tool_names:
                key = "path"  # both Sionnach tools take a path-like first arg
                return AssistantTurn(
                    tool_calls=[ToolCall(self._next_id(), tool, {key: arg})]
                )

        # Generic: "use <tool_name> {json}" escape hatch for any registered tool.
        for name in tool_names:
            if text.strip().startswith(name):
                rest = text.strip()[len(name):].strip()
                args: dict[str, Any] = {}
                if rest:
                    try:
                        args = json.loads(rest)
                    except json.JSONDecodeError:
                        args = {"path": rest.strip('"')}
                return AssistantTurn(
                    tool_calls=[ToolCall(self._next_id(), name, args)]
                )

        return AssistantTurn(text=_help(tools))


def _summarise(results: list[Any]) -> str:
    """Pull the human-readable payload out of each tool result."""
    parts: list[str] = []
    for r in results:
        try:
            data = json.loads(r.content)
        except (json.JSONDecodeError, AttributeError):
            parts.append(str(getattr(r, "content", r)))
            continue
        if isinstance(data, dict) and data.get("rendered"):
            parts.append(str(data["rendered"]))
        elif isinstance(data, dict) and data.get("error"):
            parts.append(f"[{r.name}] error: {data['error']}")
        else:
            parts.append(json.dumps(data, indent=2))
    return "\n\n".join(parts) if parts else "(no output)"


def _help(tools: list[dict[str, Any]]) -> str:
    lines = [
        "Athena is running offline (no model key set), so I can run tools "
        "directly but can't free-form reason.",
        "",
        "Try a direct command, e.g.:",
        "  scan <path-to-project>",
        "  fleet <path-to-folder-of-projects>",
        "",
        "Available tools:",
    ]
    for t in tools:
        lines.append(f"  • {t['name']} — {t['description'].splitlines()[0]}")
    lines.append("")
    lines.append("Set ANTHROPIC_API_KEY (or OPENAI_API_KEY) for full reasoning.")
    return "\n".join(lines)
