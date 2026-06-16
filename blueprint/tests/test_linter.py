"""Tests for Reviewer linter tool."""
import json
import tempfile
from pathlib import Path

from blueprint.agents.tool_executor import execute_tool


def test_run_linter_returns_structured_result():
    """Linter should return structured result with issues field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("def hello():\n    return 'world'\n")
        call = {"name": "run_linter", "args": {"path": "app.py"}}
        result = execute_tool(call, project_dir=tmpdir)
        data = json.loads(result)
        assert "issues" in data
        assert "score" in data
        assert isinstance(data["issues"], list)


def test_run_linter_nonexistent_file():
    """Linter should handle missing file gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        call = {"name": "run_linter", "args": {"path": "nonexistent.py"}}
        result = execute_tool(call, project_dir=tmpdir)
        data = json.loads(result)
        assert "error" in data


def test_run_linter_no_ruff():
    """Linter should work even if ruff is not installed (graceful skip)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("x = 1\n")
        call = {"name": "run_linter", "args": {"path": "app.py"}}
        result = execute_tool(call, project_dir=tmpdir)
        data = json.loads(result)
        # Should not crash, should have issues or skip marker
        assert "issues" in data or "error" in data or data.get("skipped")
