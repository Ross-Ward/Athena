"""App tools — config-driven, fail-safe. No real GUI apps are launched here."""
import json
import sys

from athena.tools.apps_tool import AppTool, load_apps_config, register_apps
from athena.tools.base import ToolRegistry


def _write_config(tmp_path, apps):
    p = tmp_path / "apps.json"
    p.write_text(json.dumps({"apps": apps}), encoding="utf-8")
    return p


def test_missing_config_is_empty(tmp_path):
    assert load_apps_config(tmp_path / "nope.json") == []


def test_register_apps_from_config(tmp_path):
    cfg = _write_config(tmp_path, [
        {"name": "demo", "exec": sys.executable, "mode": "capture",
         "args": ["-c", "print('hi')"]},
    ])
    reg = ToolRegistry()
    n = register_apps(reg, path=cfg)
    assert n == 1
    assert "app_demo" in reg


def test_capture_app_runs_and_returns_stdout(tmp_path):
    cfg = _write_config(tmp_path, [
        {"name": "py", "exec": sys.executable, "mode": "capture"},
    ])
    reg = ToolRegistry()
    register_apps(reg, path=cfg)
    out = reg.get("app_py").run(args=["-c", "print('athena')"])
    assert out["ok"] is True
    assert "athena" in out["stdout"]


def test_missing_executable_fails_safe():
    tool = AppTool({"name": "ghost", "exec": "definitely_not_a_real_exe_xyz",
                    "mode": "capture"})
    out = tool.run()
    assert out["ok"] is False
    assert "not found" in out["error"]


def test_invalid_entries_skipped(tmp_path):
    cfg = _write_config(tmp_path, [
        {"name": "ok", "exec": sys.executable},
        {"name": "noexec"},          # missing exec → filtered by loader
        {"exec": "x"},               # missing name → filtered by loader
    ])
    reg = ToolRegistry()
    n = register_apps(reg, path=cfg)
    assert n == 1
