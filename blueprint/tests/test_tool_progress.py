from unittest.mock import MagicMock
from blueprint.agents.tool_executor import execute_tool, set_progress_callback

def test_progress_callback_called():
    callback = MagicMock()
    set_progress_callback(callback)
    call = {"name": "file_write", "args": {"path": "test_cb.py", "content": "x=1"}}
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_tool(call, project_dir=tmpdir)
            assert callback.called
            call_kwargs = callback.call_args[1]
            assert "tool" in call_kwargs
    finally:
        set_progress_callback(None)

def test_progress_callback_exception_safe():
    def bad_callback(**kw):
        raise RuntimeError("callback exploded")
    set_progress_callback(bad_callback)
    call = {"name": "file_write", "args": {"path": "test.py", "content": "x=1"}}
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_tool(call, project_dir=tmpdir)
            assert result is not None
    finally:
        set_progress_callback(None)

def test_no_callback(tmp_path):
    set_progress_callback(None)
    call = {"name": "file_write", "args": {"path": "test.py", "content": "x=1"}}
    result = execute_tool(call, project_dir=str(tmp_path))
    assert result is not None
    assert (tmp_path / "test.py").exists()
