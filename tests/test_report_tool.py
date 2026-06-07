"""Portfolio report tool — offline, deterministic; skipped without Sionnach."""
import pytest

from athena.tools import default_registry
from athena.tools.report_tool import build_portfolio_report

pytest.importorskip("sionnach", reason="Sionnach not installed")


def test_report_tool_registered():
    assert "portfolio_report" in default_registry()


def test_no_roots_fails_safe():
    out = build_portfolio_report(roots=[])
    assert out["ok"] is False
    assert "error" in out


def test_report_rolls_up_and_renders(tmp_path):
    (tmp_path / "proj_a").mkdir()
    (tmp_path / "proj_b").mkdir()
    out = build_portfolio_report(roots=[str(tmp_path)])
    assert out["ok"] is True
    assert out["totals"]["projects"] == 2
    assert "Portfolio Status" in out["rendered"]
    assert out["out_path"] is None  # not written when out omitted


def test_report_writes_file(tmp_path):
    (tmp_path / "proj_a").mkdir()
    dest = tmp_path / "out" / "STATUS.md"
    out = build_portfolio_report(roots=[str(tmp_path)], out=str(dest))
    assert out["ok"] is True
    assert out["out_path"] == str(dest)
    assert dest.read_text(encoding="utf-8").startswith("# 🦉 Portfolio Status")


def test_report_handles_bad_root():
    out = build_portfolio_report(roots=["F:/no/such/folder/xyz"])
    # A bad root is reported as a section error, not a crash.
    assert out["ok"] is True
    assert any(not r["ok"] for r in out["per_root"])
