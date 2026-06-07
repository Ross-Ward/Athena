from athena.tools.base import Tool, ToolRegistry
from athena.transports.base import ToolCall


class EchoTool(Tool):
    name = "echo"
    description = "Echo back the message."
    input_schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    def run(self, **kwargs):
        return {"ok": True, "echo": kwargs["message"]}


def test_register_and_specs():
    reg = ToolRegistry()
    reg.register(EchoTool())
    assert "echo" in reg
    assert len(reg) == 1
    specs = reg.specs()
    assert specs[0]["name"] == "echo"
    assert specs[0]["input_schema"]["required"] == ["message"]


def test_duplicate_registration_rejected():
    reg = ToolRegistry()
    reg.register(EchoTool())
    try:
        reg.register(EchoTool())
    except ValueError:
        return
    raise AssertionError("expected duplicate registration to raise")


def test_execute_success_returns_json_result():
    reg = ToolRegistry()
    reg.register(EchoTool())
    res = reg.execute(ToolCall("c1", "echo", {"message": "hi"}))
    assert res.id == "c1"
    assert res.name == "echo"
    assert '"echo": "hi"' in res.content


def test_execute_unknown_tool_is_graceful():
    reg = ToolRegistry()
    res = reg.execute(ToolCall("c2", "nope", {}))
    assert '"ok": false' in res.content.lower()
    assert "unknown tool" in res.content


def test_execute_bad_arguments_is_graceful():
    reg = ToolRegistry()
    reg.register(EchoTool())
    res = reg.execute(ToolCall("c3", "echo", {}))  # missing required 'message'
    assert '"ok": false' in res.content.lower()
