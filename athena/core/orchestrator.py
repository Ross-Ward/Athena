"""Orchestrator — Athena's agent loop.

The core that makes Athena an *orchestrator* rather than a chatbot: it runs the
tool-use loop, delegating to registered sub-agents/tools (Sionnach today) until
the model produces a final answer or the step budget is exhausted.

    user task
       │
       ▼
    ┌─────────────────────────────────────────────┐
    │ transport.complete(system, history, tools)  │◀──┐
    └─────────────────────────────────────────────┘   │
       │ tool_calls?                                   │ results fed back
       ├── yes ─▶ registry.execute(each) ─▶ history ───┘
       └── no  ─▶ final answer

Design patterns: **Mediator** (coordinates transport + tools + session without
them knowing each other), **Strategy** (the transport), **Registry** (tools).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from athena.core.session import Session
from athena.tools.base import ToolRegistry
from athena.transports.base import ModelTransport

SYSTEM_PROMPT = (
    "You are Athena, Ross Ward's personal AI orchestrator. You coordinate work "
    "by delegating to specialised tools and sub-agents rather than guessing. "
    "When a project's production-readiness is in question, call the Sionnach "
    "tools instead of reasoning it out yourself. Be concise and concrete; when "
    "you have enough information, give a direct final answer with the most "
    "important next actions first."
)

DEFAULT_MAX_STEPS = 8


@dataclass(slots=True)
class RunResult:
    text: str
    steps: int
    session: Session
    tool_calls_made: int = 0
    stopped: str = "final"  # "final" | "max_steps"


@dataclass(slots=True)
class Orchestrator:
    """Mediator over a transport + a tool registry + a session."""

    transport: ModelTransport
    registry: ToolRegistry
    system: str = SYSTEM_PROMPT
    max_steps: int = field(
        default_factory=lambda: _int_env("ATHENA_MAX_STEPS", DEFAULT_MAX_STEPS)
    )

    def run(self, task: str, session: Session | None = None) -> RunResult:
        session = session or Session()
        session.add_user(task)
        specs = self.registry.specs()
        tool_calls_made = 0

        for step in range(1, self.max_steps + 1):
            turn = self.transport.complete(
                system=self.system,
                messages=session.messages,
                tools=specs,
            )

            if turn.tool_calls:
                session.add_assistant(turn.text, turn.tool_calls)
                results = [self.registry.execute(c) for c in turn.tool_calls]
                tool_calls_made += len(results)
                session.add_tool_results(results)
                continue

            session.add_assistant(turn.text)
            return RunResult(
                text=turn.text,
                steps=step,
                session=session,
                tool_calls_made=tool_calls_made,
                stopped="final",
            )

        return RunResult(
            text="(stopped: reached max tool-use steps)",
            steps=self.max_steps,
            session=session,
            tool_calls_made=tool_calls_made,
            stopped="max_steps",
        )


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except (TypeError, ValueError):
        return default
