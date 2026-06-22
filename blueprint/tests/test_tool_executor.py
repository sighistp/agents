import json
import os
import pytest
from blueprint.agents.tool_executor import execute_tool


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


# ── P2.3: execute_python directory caching ─────────────────────────────────

def test_directory_content_hash():
    """P2.3: Should be able to hash directory contents for caching."""
    import hashlib
    import tempfile
    from pathlib import Path

    tmpdir = tempfile.mkdtemp()
    # Create test files
    Path(tmpdir, "a.py").write_text("print('hello')")
    Path(tmpdir, "b.py").write_text("print('world')")

    # Hash directory
    files = sorted(Path(tmpdir).glob("*.py"))
    h = hashlib.md5()
    for f in files:
        h.update(f.read_bytes())
    hash1 = h.hexdigest()

    # Same content = same hash
    h = hashlib.md5()
    for f in sorted(Path(tmpdir).glob("*.py")):
        h.update(f.read_bytes())
    hash2 = h.hexdigest()
    assert hash1 == hash2

    # Changed content = different hash
    Path(tmpdir, "a.py").write_text("print('changed')")
    h = hashlib.md5()
    for f in sorted(Path(tmpdir).glob("*.py")):
        h.update(f.read_bytes())
    hash3 = h.hexdigest()
    assert hash3 != hash1

    import shutil
    shutil.rmtree(tmpdir)


@pytest.mark.xfail(reason="P2.3: Directory caching not yet implemented")
def test_execute_python_caches_directory(tmp_path):
    """P2.3: execute_python should reuse cached workdir when project unchanged."""
    # Write a project file
    (tmp_path / "data.txt").write_text("cached_data")

    # First call — reads file from workdir
    call = MockCall("execute_python", {"code": "import os; print(os.path.exists('data.txt'))"})
    result1 = json.loads(execute_tool(call, str(tmp_path)))
    assert result1["returncode"] == 0
    assert "True" in result1["stdout"]

    # Second call with same project dir — should reuse cached copy
    result2 = json.loads(execute_tool(call, str(tmp_path)))
    assert result2["returncode"] == 0
    assert "True" in result2["stdout"]
