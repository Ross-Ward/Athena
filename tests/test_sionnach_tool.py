"""Integration with the real Sionnach sub-agent — skipped if it isn't installed."""
import pytest

from athena.tools import default_registry
from athena.tools.sionnach_tool import register_sionnach
from athena.tools.base import ToolRegistry

sionnach = pytest.importorskip("sionnach", reason="Sionnach not installed")


def test_register_sionnach_adds_both_tools():
    reg = ToolRegistry()
    ok = register_sionnach(reg)
    assert ok is True
    assert "sionnach_scan" in reg
    assert "sionnach_fleet" in reg


def test_default_registry_includes_sionnach():
    reg = default_registry()
    assert "sionnach_scan" in reg


def test_scan_self_returns_backlog(tmp_path):
    # Scan an empty temp dir: deterministic, offline, should flag gaps without raising.
    reg = default_registry()
    tool = reg.get("sionnach_scan")
    out = tool.run(path=str(tmp_path), format="json")
    assert out["ok"] is True
    assert "counts" in out
    assert isinstance(out["task_count"], int)


def test_fleet_ranks_subdirectories(tmp_path):
    (tmp_path / "proj_a").mkdir()
    (tmp_path / "proj_b").mkdir()
    reg = default_registry()
    tool = reg.get("sionnach_fleet")
    out = tool.run(path=str(tmp_path), format="table")
    assert out["ok"] is True
    assert out["project_count"] == 2
    assert "PROJECT" in out["rendered"]
