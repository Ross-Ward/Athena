"""App tools — let Athena invoke Ross's other applications.

This is the "connect all my applications" layer. Each app Athena can drive is a
*data* entry in a JSON config (``~/.athena/apps.json`` by default), and each entry
becomes one delegatable :class:`AppTool` in the registry. So adding a new app to
the orchestrator is a config edit, not a code change.

An app entry:

```json
{
  "name": "spideog",
  "description": "Launch the Spidéog terminal.",
  "exec": "C:\\\\Users\\\\me\\\\AppData\\\\Local\\\\Spideog\\\\bin\\\\spideog.cmd",
  "args": [],
  "mode": "launch",      // "launch" = detached (GUI), "capture" = run + capture stdout
  "cwd": null
}
```

Design pattern: **Adapter + Registry-from-config**. ``AppTool`` adapts a CLI/GUI
to the uniform ``run(**kwargs) -> dict``; ``register_apps`` builds tools from the
config. Always fails safe — bad config or a missing executable yields
``{"ok": False, "error": ...}`` rather than raising.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from athena.tools.base import Tool, ToolRegistry

#: Where the app catalogue lives (override with ATHENA_APPS_CONFIG).
DEFAULT_CONFIG = Path(os.environ.get("ATHENA_HOME", Path.home() / ".athena")) / "apps.json"
_CAPTURE_TIMEOUT = 120  # seconds; capture-mode apps must not hang the loop


def config_path() -> Path:
    env = os.environ.get("ATHENA_APPS_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG


def load_apps_config(path: Path | None = None) -> list[dict[str, Any]]:
    """Read the app catalogue. Missing/invalid config → empty list (no apps)."""
    p = path or config_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    apps = raw.get("apps", raw) if isinstance(raw, dict) else raw
    return [a for a in apps if isinstance(a, dict) and a.get("name") and a.get("exec")]


class AppTool(Tool):
    """One configured application, exposed as a delegatable tool."""

    def __init__(self, entry: dict[str, Any]) -> None:
        self._exec = str(entry["exec"])
        self._base_args = [str(a) for a in entry.get("args", [])]
        self._mode = entry.get("mode", "launch")
        self._cwd = entry.get("cwd")
        self.name = f"app_{entry['name']}"
        verb = "Launch" if self._mode == "launch" else "Run"
        self.description = entry.get("description") or f"{verb} the {entry['name']} app."
        self.input_schema = {
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra command-line arguments to pass to the app.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory to run the app from (optional).",
                },
            },
        }

    def _resolve_exec(self) -> str | None:
        if Path(self._exec).exists():
            return self._exec
        return shutil.which(self._exec)  # allow bare names on PATH

    def run(self, **kwargs: Any) -> dict[str, Any]:
        exe = self._resolve_exec()
        if not exe:
            return {"ok": False, "error": f"executable not found: {self._exec}"}
        extra = [str(a) for a in (kwargs.get("args") or [])]
        cmd = [exe, *self._base_args, *extra]
        cwd = kwargs.get("cwd") or self._cwd or None

        try:
            if self._mode == "capture":
                proc = subprocess.run(
                    cmd, cwd=cwd, capture_output=True, text=True,
                    timeout=_CAPTURE_TIMEOUT,
                )
                ok = proc.returncode == 0
                return {
                    "ok": ok,
                    "app": self.name,
                    "command": cmd,
                    "returncode": proc.returncode,
                    "stdout": (proc.stdout or "")[-8000:],
                    "stderr": (proc.stderr or "")[-2000:],
                    "rendered": (proc.stdout or proc.stderr or "").strip()
                                or f"{self.name} exited {proc.returncode}",
                }
            # launch mode: fire-and-forget (don't block the orchestrator)
            subprocess.Popen(cmd, cwd=cwd)
            return {
                "ok": True,
                "app": self.name,
                "command": cmd,
                "rendered": f"Launched {self.name}.",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"{self.name} timed out after {_CAPTURE_TIMEOUT}s"}
        except OSError as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def register_apps(registry: ToolRegistry, path: Path | None = None) -> int:
    """Register one AppTool per configured app. Returns how many were added."""
    added = 0
    for entry in load_apps_config(path):
        try:
            registry.register(AppTool(entry))
            added += 1
        except (ValueError, KeyError):
            continue  # duplicate/invalid entry — skip, stay alive
    return added
