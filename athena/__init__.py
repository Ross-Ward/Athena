"""Athena — Ross Ward's own AI orchestrator agent.

A small, handwritten orchestrator that coordinates work by delegating to focused
tools and sub-agents (Sionnach today) through a clean tool registry. Offline and
deterministic by default; add an Anthropic or OpenAI-compatible key to unlock the
full reasoning loop.

Athena is the in-house replacement for the third-party Hermes Agent clone — same
ambition (a personal AI that delegates and self-improves), rebuilt as Ross's own
product with a tighter, pattern-driven architecture.
"""
from athena.core import Orchestrator, RunResult, Session
from athena.tools import ToolRegistry, default_registry
from athena.transports import select_transport

__version__ = "0.1.0"

__all__ = [
    "Orchestrator",
    "RunResult",
    "Session",
    "ToolRegistry",
    "default_registry",
    "select_transport",
    "__version__",
]
