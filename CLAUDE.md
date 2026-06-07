# CLAUDE.md — Athena

Guidance for working in this repo.

## What Athena is

Ross Ward's own AI **orchestrator** — the in-house replacement for the
third-party Hermes Agent clone. It coordinates work by delegating to focused
tools and sub-agents (Sionnach today) through a tool registry and a model-agnostic
agent loop. Offline-deterministic by default; a key unlocks real reasoning.

This is `v0.1`: the clean core (transports + tools + orchestrator + memory + CLI).
The larger Athena vision (messaging gateways, cron, skill registry, web dashboard)
builds on this loop — see `hermes-agent/PLAN.md`.

## Run / test

```bash
python -m pip install -e ".[dev]"     # core + tests
python -m pip install -e ../sionnach  # the first sub-agent
python -m pytest -q                   # full suite (offline; Sionnach tests skip if absent)
athena --offline ask "scan ."         # dogfood the loop with no key
```

## Architecture & design patterns

| Pattern | Where | Why |
|---|---|---|
| **Mediator** | `core/orchestrator.py` | Runs the tool-use loop; couples transport+tools+session without them knowing each other. |
| **Strategy / Adapter** | `transports/{anthropic,openai_compat,offline}.py` | Interchangeable backends behind `ModelTransport`. SDKs imported lazily. |
| **Factory** | `transports/registry.py::select_transport` | Env → best available backend; always returns a usable transport. |
| **Registry + Command** | `tools/base.py` | `Tool` is a command; `ToolRegistry` resolves+executes calls by name, failing safe. |
| **Adapter** | `tools/sionnach_tool.py` | Wraps Sionnach's `integrations.athena` bridge into Athena tools. |
| **Repository** | `memory/store.py` | Session history behind an interface (JSONL now; SQLite/Chroma later). |
| **Value objects** | `transports/base.py` | `Message`/`ToolCall`/`ToolResult`/`AssistantTurn`, transport-neutral. |

## The agent loop (core/orchestrator.py)

```
Session(user task)
  repeat up to max_steps:
    turn = transport.complete(system, messages, registry.specs())
    if turn.tool_calls:
        record assistant(tool_calls); execute each via registry; record tool results; continue
    else:
        record assistant(text); return RunResult(final)
```

The **offline transport** makes this loop runnable/testable without a key: it
turns `scan <path>` / `fleet <dir>` into real tool calls and summarises results.

## Adding a tool / sub-agent

1. Subclass `Tool` (set `name`, `description`, `input_schema`, implement `run`).
   `run` returns a JSON-serialisable dict and should **fail safe**
   (`{"ok": False, "error": ...}`) rather than raise.
2. Register it — add to `tools/default_registry()` (or a `register_*` helper that
   no-ops when an optional dependency is missing, like `register_sionnach`).
3. Add a test in `tests/`.

## Conventions

- **No required third-party deps in the core.** LLM SDKs are optional extras,
  imported lazily; Athena must install and run with none of them.
- Transports translate the neutral history to their own format — never leak a
  vendor type into `core/` or `tools/`.
- Keep tools **delegation-shaped**: prefer calling a specialist sub-agent over
  re-implementing its logic here.
- Model ids: default to current Claude (`claude-sonnet-4-6`); never hard-code a
  retired id.

## Relationship to Sionnach

Athena consumes Sionnach via `sionnach.integrations.athena` (`run_scan`,
`run_fleet`, tool specs). The legacy `sionnach.integrations.hermes` is a
deprecated shim re-exporting that module. If you change the bridge contract,
update `tools/sionnach_tool.py` to match.
