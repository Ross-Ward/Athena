# Athena

> **Ross Ward's own AI orchestrator agent.** Coordinates work by *delegating* to
> focused sub-agents and tools through a clean registry — instead of reasoning out
> everything itself. Offline & deterministic by default; add a key for full reasoning.

Athena is a personal AI that delegates, schedules, and self-improves — built
from scratch with a tight, pattern-driven core, replacing an earlier third-party
agent stack.
Its first sub-agent is **[Sionnach](../sionnach)** (the fox), which it calls to
triage any project's production-readiness.

## Why it exists

A big orchestrator shouldn't hand-reason boring-but-critical questions like
*"what's left before this ships?"* — it should **delegate** to a specialist and
act on the answer. Athena is the thin, reliable core that does the delegating: a
tool registry, a transport abstraction over LLM backends, and an agent loop that
runs tool calls until it has a real answer.

## Safe by default

- **Runs with no key.** With no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, Athena
  uses an offline-deterministic engine: `athena scan <path>` and `athena fleet
  <dir>` call Sionnach directly, same input → same output, no network.
- **Add a key for reasoning.** Set a key and the same tools are driven by a real
  model loop (Anthropic primary, any OpenAI-compatible endpoint as fallback).
- **Tools fail safe.** A tool error returns `{ok: false, error}` and the loop
  keeps going — it never crashes mid-task.

## Install

```bash
cd athena
python -m pip install -e ".[dev]"          # core + tests
python -m pip install -e ".[dev,anthropic]"  # + Anthropic backend
# Sionnach (the first sub-agent) — install it editable from the sibling folder:
python -m pip install -e ../sionnach
```

## Usage

```bash
athena tools                       # what Athena can delegate to
athena scan /path/to/project       # Sionnach backlog for one project (no key needed)
athena fleet /path/to/portfolio    # rank a folder of projects worst-first
athena ask "Triage this project and tell me the top 3 things to fix"
athena version                     # version + active backend
```

`ask` runs the full orchestrator loop: it picks the best backend, exposes the
Sionnach tools to the model, executes whatever the model calls, and returns a
final answer. Offline, `ask` understands direct directives like `scan <path>`.

## Architecture & design patterns

| Pattern | Where | Why |
|---|---|---|
| **Mediator** | `core/orchestrator.py::Orchestrator` | Coordinates transport + tools + session; none know each other. |
| **Strategy / Adapter** | `transports/*` | One `ModelTransport` interface; Anthropic / OpenAI-compat / offline are interchangeable adapters. |
| **Registry** | `tools/base.py::ToolRegistry` | Tools/sub-agents register by name; calls resolve and execute uniformly. |
| **Command** | `tools/base.py::Tool` | Each capability is an executable unit with a declared schema. |
| **Adapter** | `tools/sionnach_tool.py` | Wraps Sionnach's bridge into Athena tools. |
| **Repository** | `memory/store.py` | Session history behind an interface (JSONL now, SQLite/Chroma later). |
| **Value objects** | `transports/base.py` | `Message` / `ToolCall` / `ToolResult` are transport-neutral, so history is portable. |
| **Factory** | `transports/registry.py::select_transport` | Picks a backend from the environment; always returns a usable transport. |

## Data flow

```
task → Session(user) → loop:
   transport.complete(system, history, tool specs)
     ├─ tool_calls → registry.execute(each) → history(tool results) → loop
     └─ final text → RunResult (+ persisted to ~/.athena/sessions.jsonl)
```

## Roadmap

Athena's `PLAN.md` tracks the roadmap:
messaging gateways (Telegram/Discord), cron scheduling, a skill registry, a web
dashboard, and packaging as a self-hosted Docker image. This `v0.1` is the clean
core + Sionnach delegation; the rest builds on this loop.

## License

MIT © Ross Ward.
