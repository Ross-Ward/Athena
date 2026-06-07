import os

from athena.transports import select_transport
from athena.transports.anthropic import AnthropicTransport
from athena.transports.offline import OfflineTransport
from athena.transports.openai_compat import OpenAICompatTransport


def test_force_offline_selects_offline():
    t = select_transport(force_offline=True)
    assert isinstance(t, OfflineTransport)
    assert t.name == "offline"


def test_select_falls_back_to_offline_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ATHENA_OFFLINE", raising=False)
    assert isinstance(select_transport(), OfflineTransport)


def test_athena_offline_env_forces_offline(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv("ATHENA_OFFLINE", "1")
    assert isinstance(select_transport(), OfflineTransport)


def test_backend_availability_reflects_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert AnthropicTransport().available is False
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAICompatTransport().available is False


def test_offline_summarises_tool_result():
    from athena.transports.base import Message, ToolResult

    t = OfflineTransport()
    msg = Message(
        role="tool",
        tool_results=[ToolResult("1", "sionnach_scan",
                                 '{"ok": true, "rendered": "DONE"}')],
    )
    turn = t.complete(system="", messages=[msg], tools=[])
    assert turn.tool_calls == []
    assert "DONE" in turn.text
