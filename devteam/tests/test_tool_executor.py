import json
import os
import pytest
from devteam.agents.tool_executor import execute_tool, _validate_path


class MockCall:
    def __init__(self, name, arguments):
        self.id = "call_test"
        self.function = type("F", (), {"name": name, "arguments": json.dumps(arguments)})()


def test_file_write(tmp_path):
    call = MockCall("file_write", {"path": "main.py", "content": "print('hello')"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["success"] is True
    assert (tmp_path / "main.py").read_text() == "print('hello')"


def test_file_write_nested_path(tmp_path):
    call = MockCall("file_write", {"path": "src/utils.py", "content": "x=1"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["success"] is True
    assert (tmp_path / "src" / "utils.py").read_text() == "x=1"


def test_file_read(tmp_path):
    (tmp_path / "test.txt").write_text("hello world")
    call = MockCall("file_read", {"path": "test.txt"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["content"] == "hello world"


def test_file_read_not_found(tmp_path):
    call = MockCall("file_read", {"path": "nonexistent.py"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert "error" in result


def test_execute_python(tmp_path):
    call = MockCall("execute_python", {"code": "print(1+1)"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["returncode"] == 0
    assert "2" in result["stdout"]


def test_done():
    call = MockCall("done", {"summary": "完成了", "files_modified": ["a.py"]})
    result = json.loads(execute_tool(call, "/tmp"))
    assert result["status"] == "completed"
    assert result["summary"] == "完成了"


def test_unknown_tool():
    call = MockCall("unknown_tool", {})
    result = json.loads(execute_tool(call, "/tmp"))
    assert "error" in result


def test_validate_path_rejects_dotdot():
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("../etc/passwd", "/tmp")


def test_validate_path_rejects_absolute():
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("/etc/passwd", "/tmp")


def test_validate_path_rejects_empty():
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("", "/tmp")
