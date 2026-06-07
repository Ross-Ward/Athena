"""End-to-end orchestrator loop, fully offline and deterministic (no key/network).

Uses a fake tool so the test doesn't depend on Sionnach, exercising the real loop:
user directive → offline transport emits a tool call → registry executes it →
transport summarises the result → loop ends with a final answer.
"""
from athena.core import Orchestrator
from athena.tools.base import Tool, ToolRegistry
from athena.transports.offline import OfflineTransport


class FakeScanTool(Tool):
    name = "sionnach_scan"
    description = "Fake readiness scan for tests."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, **kwargs):
        return {
            "ok": True,
            "project": kwargs["path"],
            "rendered": f"BACKLOG for {kwargs['path']}: 1 blocker, 2 high",
        }


def _orch():
    reg = ToolRegistry()
    reg.register(FakeScanTool())
    return Orchestrator(transport=OfflineTransport(), registry=reg)


def test_scan_directive_drives_tool_call_then_finishes():
    result = _orch().run("scan ./some/project")
    assert result.tool_calls_made == 1
    assert result.stopped == "final"
    assert "BACKLOG for ./some/project" in result.text
    # history shape: user → assistant(tool_call) → tool(result) → assistant(final)
    roles = [m.role for m in result.session.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_non_directive_returns_help_without_tool_calls():
    result = _orch().run("hello there")
    assert result.tool_calls_made == 0
    assert "offline" in result.text.lower()
    assert "sionnach_scan" in result.text


def test_unknown_tool_directive_falls_back_to_help():
    # 'fleet' maps to sionnach_fleet which isn't registered here → help, no crash.
    result = _orch().run("fleet ./folder")
    assert result.tool_calls_made == 0
    assert "available tools" in result.text.lower()
