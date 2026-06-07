"""Saoirse tools — registration is env-gated; no network is hit in these tests."""
from athena.tools.base import ToolRegistry
from athena.tools.saoirse_tool import (
    SaoirseTodosTool,
    register_saoirse,
    _request,
)


def test_no_config_does_not_register(monkeypatch):
    monkeypatch.delenv("SAOIRSE_URL", raising=False)
    monkeypatch.delenv("SAOIRSE_API_TOKEN", raising=False)
    reg = ToolRegistry()
    assert register_saoirse(reg) is False
    assert len(reg) == 0


def test_config_registers_all_tools(monkeypatch):
    monkeypatch.setenv("SAOIRSE_URL", "http://127.0.0.1:7000")
    monkeypatch.setenv("SAOIRSE_API_TOKEN", "sao_test")
    reg = ToolRegistry()
    assert register_saoirse(reg) is True
    for name in (
        "saoirse_capabilities", "saoirse_todos", "saoirse_memory",
        "saoirse_documents", "saoirse_calendar", "saoirse_email",
    ):
        assert name in reg


def test_request_without_config_fails_safe(monkeypatch):
    monkeypatch.delenv("SAOIRSE_URL", raising=False)
    monkeypatch.delenv("SAOIRSE_API_TOKEN", raising=False)
    out = _request("GET", "/api/codex/capabilities")
    assert out["ok"] is False
    assert "error" in out


def test_request_rejects_non_codex_path(monkeypatch):
    monkeypatch.setenv("SAOIRSE_URL", "http://127.0.0.1:7000")
    monkeypatch.setenv("SAOIRSE_API_TOKEN", "sao_test")
    out = _request("GET", "/api/secret/keys")
    assert out["ok"] is False
    assert "codex" in out["error"]


def test_todos_add_requires_title(monkeypatch):
    monkeypatch.setenv("SAOIRSE_URL", "http://127.0.0.1:7000")
    monkeypatch.setenv("SAOIRSE_API_TOKEN", "sao_test")
    out = SaoirseTodosTool().run(action="add", title="   ")
    assert out["ok"] is False
