"""Portfolio report — Athena's first cross-project automation.

Athena delegates per-project triage to Sionnach (``sionnach_fleet``). This tool
sits one level up: it fleets one or more *roots*, rolls the results into a single
ranked **PORTFOLIO_STATUS.md**, and writes it to disk. That is the "what do I fix
next across everything" artifact.

Why a separate tool (not just `fleet`):
* `fleet` ranks the immediate children of ONE folder and renders to stdout.
* A real portfolio is nested by category, so the report accepts MANY roots and
  concatenates a section per root under one summary roll-up — then persists it.

Design pattern: **Adapter + Builder**. It adapts Sionnach's ``run_fleet`` bridge
and builds a composite document. It depends only on Sionnach being importable;
if it isn't, the tool fails safe with ``{"ok": False, "error": ...}``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from athena.tools.base import Tool, ToolRegistry


def _bridge() -> Any:
    """Lazy import of Sionnach's Athena bridge (preferred) or legacy hermes shim."""
    try:
        from sionnach.integrations import athena as bridge  # type: ignore
        return bridge
    except ImportError:
        from sionnach.integrations import hermes as bridge  # type: ignore
        return bridge


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def build_portfolio_report(
    roots: list[str],
    out: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Fleet every ``root``, roll the results into one markdown report, and
    (optionally) write it to ``out``. Always returns a JSON-serialisable dict;
    never raises for ordinary input problems."""
    if not roots:
        return {"ok": False, "error": "no roots given to report on"}

    try:
        run_fleet = getattr(_bridge(), "run_fleet")
    except (ImportError, AttributeError):
        return {
            "ok": False,
            "error": "Sionnach fleet bridge unavailable — install/upgrade sionnach.",
        }

    sections: list[str] = []
    totals = {"projects": 0, "ready": 0, "not_ready": 0}
    per_root: list[dict[str, Any]] = []

    for root in roots:
        res = run_fleet(path=root, format="markdown", limit=limit)
        if not res.get("ok", False):
            sections.append(f"## {root}\n\n> ⚠️ {res.get('error', 'scan failed')}\n")
            per_root.append({"root": root, "ok": False, "error": res.get("error")})
            continue
        pc = res.get("project_count", 0)
        rc = res.get("ready_count", 0)
        nr = res.get("not_ready_count", pc - rc)
        totals["projects"] += pc
        totals["ready"] += rc
        totals["not_ready"] += nr
        per_root.append(
            {"root": root, "ok": True, "project_count": pc,
             "ready_count": rc, "not_ready_count": nr}
        )
        sections.append(
            f"## {root}\n\n"
            f"_{pc} project(s) · {nr} not yet production-ready · {rc} ready_\n\n"
            f"{res.get('rendered', '').strip()}\n"
        )

    header = (
        "# 🦉 Portfolio Status\n\n"
        f"_Generated {_now_iso()} by Athena (delegating to Sionnach)._\n\n"
        f"**Roll-up:** {totals['projects']} project(s) across {len(roots)} root(s) · "
        f"**{totals['not_ready']} need work** · {totals['ready']} ready.\n"
    )
    document = header + "\n" + "\n".join(sections)

    written: str | None = None
    if out:
        try:
            out_path = Path(out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(document, encoding="utf-8")
            written = str(out_path)
        except OSError as exc:
            return {"ok": False, "error": f"could not write {out}: {exc}",
                    "rendered": document}

    return {
        "ok": True,
        "roots": roots,
        "totals": totals,
        "per_root": per_root,
        "out_path": written,
        "rendered": document,
    }


class PortfolioReportTool(Tool):
    name = "portfolio_report"
    description = (
        "Run a production-readiness fleet scan across one or more portfolio "
        "roots and write a single ranked PORTFOLIO_STATUS.md. Use to get the "
        "cross-project 'what should I fix next everywhere' picture in one file."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "roots": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Folders to fleet; each is scanned worst-first and "
                               "becomes a section of the report.",
            },
            "out": {
                "type": "string",
                "description": "Where to write the markdown report. If omitted, "
                               "the report is returned but not saved.",
            },
            "limit": {
                "type": "integer",
                "description": "Max projects per root (worst-first). Optional.",
            },
        },
        "required": ["roots"],
    }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        roots = kwargs.get("roots") or []
        if isinstance(roots, str):  # tolerate a single string from a model
            roots = [roots]
        return build_portfolio_report(
            roots=list(roots),
            out=kwargs.get("out"),
            limit=kwargs.get("limit"),
        )


def register_report(registry: ToolRegistry) -> bool:
    """Register the portfolio report tool if Sionnach is importable."""
    try:
        _bridge()
    except ImportError:
        return False
    registry.register(PortfolioReportTool())
    return True
