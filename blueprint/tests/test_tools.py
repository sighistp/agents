import json
import pytest
from blueprint.agents.tools import (
    FILE_WRITE, FILE_READ, EXECUTE_PYTHON, DONE,
    DEVELOPER_TOOLS, TESTER_TOOLS, REVIEWER_TOOLS,
    serialize_call,
)


def test_file_write_schema():
    assert FILE_WRITE["type"] == "function"
    assert FILE_WRITE["function"]["name"] == "file_write"
    params = FILE_WRITE["function"]["parameters"]
    assert "path" in params["properties"]
    assert "content" in params["properties"]
    assert params["required"] == ["path", "content"]


def test_file_read_schema():
    assert FILE_READ["function"]["name"] == "file_read"
    params = FILE_READ["function"]["parameters"]
    assert "path" in params["properties"]
    assert params["required"] == ["path"]


def test_execute_python_schema():
    assert EXECUTE_PYTHON["function"]["name"] == "execute_python"
    params = EXECUTE_PYTHON["function"]["parameters"]
    assert "code" in params["properties"]
    assert params["required"] == ["code"]


def test_done_schema():
    assert DONE["function"]["name"] == "done"
    params = DONE["function"]["parameters"]
    assert "summary" in params["properties"]
    assert "files_modified" in params["properties"]
    assert "key_decisions" in params["properties"]
    assert params["required"] == ["summary"]


def test_developer_tools():
    names = [t["function"]["name"] for t in DEVELOPER_TOOLS]
    assert names == ["file_write", "file_read", "execute_python", "done"]


def test_tester_tools():
    names = [t["function"]["name"] for t in TESTER_TOOLS]
    assert names == ["file_read", "execute_python", "done"]


def test_reviewer_tools():
    names = [t["function"]["name"] for t in REVIEWER_TOOLS]
    assert names == ["file_read", "done"]


def test_serialize_call():
    class MockCall:
        id = "call_123"
        class function:
            name = "file_write"
            arguments = '{"path": "main.py", "content": "print(1)"}'

    result = serialize_call(MockCall())
    assert result["id"] == "call_123"
    assert result["type"] == "function"
    assert result["function"]["name"] == "file_write"
    assert "main.py" in result["function"]["arguments"]
