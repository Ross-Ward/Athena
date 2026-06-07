"""Athena CLI.

    athena ask "<task>"     run the orchestrator on a task (delegates to tools)
    athena scan <path>      direct: Sionnach readiness backlog for one project
    athena fleet <path>     direct: rank a folder of projects worst-first
    athena report <paths…>  fleet several roots → one ranked PORTFOLIO_STATUS.md
    athena tools            list the tools/sub-agents Athena can delegate to
    athena version          print version + active backend

`ask` uses the best available backend (Anthropic → OpenAI-compat → offline).
`scan`/`fleet` are deterministic shortcuts that call the tool directly — no key
needed — so Athena is useful from the very first run.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from athena import __version__
from athena.core import Orchestrator, Session
from athena.memory import JsonlSessionStore, NullSessionStore
from athena.tools import build_portfolio_report, default_registry
from athena.transports import select_transport


def _print_tool_result(payload: dict[str, Any], raw: bool) -> int:
    if raw:
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok", True) else 1
    if not payload.get("ok", True):
        print(f"error: {payload.get('error', 'unknown error')}", file=sys.stderr)
        return 1
    print(payload.get("rendered") or json.dumps(payload, indent=2, default=str))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    transport = select_transport(force_offline=args.offline)
    registry = default_registry()
    orch = Orchestrator(transport=transport, registry=registry)
    result = orch.run(args.task)

    store = NullSessionStore() if args.no_save else JsonlSessionStore()
    store.save(result.session, summary=args.task[:200])

    print(result.text)
    if args.verbose:
        print(
            f"\n— {transport.name} · {result.steps} step(s) · "
            f"{result.tool_calls_made} tool call(s) · {result.stopped}",
            file=sys.stderr,
        )
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    reg = default_registry()
    tool = reg.get("sionnach_scan")
    if tool is None:
        print("Sionnach is not installed — `pip install -e` the sionnach package.",
              file=sys.stderr)
        return 2
    payload = tool.run(path=args.path, format=args.format, advisor=args.advisor)
    return _print_tool_result(payload, args.json)


def cmd_fleet(args: argparse.Namespace) -> int:
    reg = default_registry()
    tool = reg.get("sionnach_fleet")
    if tool is None:
        print("Sionnach fleet bridge unavailable — upgrade the sionnach package.",
              file=sys.stderr)
        return 2
    payload = tool.run(path=args.path, format=args.format, limit=args.limit)
    return _print_tool_result(payload, args.json)


def cmd_report(args: argparse.Namespace) -> int:
    result = build_portfolio_report(roots=args.paths, out=args.out, limit=args.limit)
    if not result.get("ok", False):
        print(f"error: {result.get('error', 'report failed')}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    if result.get("out_path"):
        t = result["totals"]
        print(f"Wrote {result['out_path']}  "
              f"({t['projects']} project(s) · {t['not_ready']} need work · {t['ready']} ready)")
    else:
        print(result.get("rendered", ""))
    return 0


def cmd_tools(_args: argparse.Namespace) -> int:
    reg = default_registry()
    if not len(reg):
        print("No tools registered. Install Sionnach to add the readiness tools.")
        return 0
    print("Athena can delegate to:")
    for t in reg.tools():
        first = t.description.splitlines()[0] if t.description else ""
        print(f"  • {t.name} — {first}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    transport = select_transport(force_offline=args.offline)
    print(f"athena {__version__}  ·  backend: {transport.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="athena", description="Athena — AI orchestrator.")
    p.add_argument("--offline", action="store_true",
                   help="force offline-deterministic mode (no model calls)")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("ask", help="run the orchestrator on a task")
    a.add_argument("task", help="what you want Athena to do")
    a.add_argument("-v", "--verbose", action="store_true",
                   help="print backend/step diagnostics to stderr")
    a.add_argument("--no-save", action="store_true",
                   help="do not persist this session to ~/.athena")
    a.set_defaults(func=cmd_ask)

    s = sub.add_parser("scan", help="Sionnach readiness backlog for one project")
    s.add_argument("path")
    s.add_argument("-f", "--format", choices=["markdown", "json", "table"],
                   default="markdown")
    s.add_argument("--advisor", action="store_true",
                   help="enable Sionnach's optional LLM enrichment (needs a key)")
    s.add_argument("--json", action="store_true", help="print the raw result dict")
    s.set_defaults(func=cmd_scan)

    f = sub.add_parser("fleet", help="rank a folder of projects worst-first")
    f.add_argument("path")
    f.add_argument("-f", "--format", choices=["markdown", "json", "table"],
                   default="table")
    f.add_argument("--limit", type=int, default=None)
    f.add_argument("--json", action="store_true", help="print the raw result dict")
    f.set_defaults(func=cmd_fleet)

    r = sub.add_parser("report",
                       help="fleet several roots into one ranked PORTFOLIO_STATUS.md")
    r.add_argument("paths", nargs="+",
                   help="one or more folders to fleet; each becomes a section")
    r.add_argument("-o", "--out", default=None,
                   help="write the report here (markdown). Omit to print to stdout.")
    r.add_argument("--limit", type=int, default=None,
                   help="max projects per root (worst-first)")
    r.add_argument("--json", action="store_true", help="print the raw result dict")
    r.set_defaults(func=cmd_report)

    t = sub.add_parser("tools", help="list delegatable tools")
    t.set_defaults(func=cmd_tools)

    v = sub.add_parser("version", help="print version and active backend")
    v.set_defaults(func=cmd_version)

    return p


def _ensure_utf8() -> None:
    """Make stdout/stderr UTF-8 safe so emoji/box-drawing in tool output don't
    crash on Windows' default cp1252 console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
