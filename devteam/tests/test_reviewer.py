"""Tests for Reviewer Agent module."""
import json
import pytest
from unittest.mock import patch, MagicMock


# ── Test Helpers ─────────────────────────────────────────────────────────────

def _make_tool_call(name, arguments, call_id="call_1"):
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _make_response(content="", tool_calls=None):
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


# ── Original Tests (prompt / import) ────────────────────────────────────────

def test_reviewer_system_prompt_exists():
    """REVIEWER_SYSTEM_PROMPT should be defined."""
    from devteam.agents.reviewer import REVIEWER_SYSTEM_PROMPT
    assert isinstance(REVIEWER_SYSTEM_PROMPT, str)
    assert len(REVIEWER_SYSTEM_PROMPT) > 0


def test_reviewer_system_prompt_contains_role():
    """Prompt should define the reviewer role."""
    from devteam.agents.reviewer import REVIEWER_SYSTEM_PROMPT
    assert "审查" in REVIEWER_SYSTEM_PROMPT


def test_reviewer_agent_import():
    """reviewer_agent should be importable."""
    from devteam.agents.reviewer import reviewer_agent
    assert callable(reviewer_agent)


# ── Tool-loop Tests ─────────────────────────────────────────────────────────

def test_reviewer_uses_tools():
    """Reviewer 应使用工具循环"""
    from devteam.agents.reviewer import reviewer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("", [_make_tool_call("done", {"summary": "代码质量良好，无critical问题"})]),
    ]

    with patch("devteam.agents.reviewer.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = reviewer_agent(state)

    assert "review_approved" in result
    assert "messages" in result


def test_reviewer_only_has_read_tool():
    """Reviewer 不应有 file_write 或 execute_python"""
    from devteam.agents.tools import REVIEWER_TOOLS
    names = [t["function"]["name"] for t in REVIEWER_TOOLS]
    assert "file_write" not in names
    assert "execute_python" not in names
    assert "file_read" in names
    assert "done" in names


def test_reviewer_handles_no_tool_calls():
    """LLM 不调工具时应当作隐式完成"""
    from devteam.agents.reviewer import reviewer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("审查通过，代码质量良好"),
    ]

    with patch("devteam.agents.reviewer.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = reviewer_agent(state)

    assert "review_approved" in result
    assert result.get("error") is None


def test_reviewer_max_steps():
    """超过最大步数应返回错误"""
    from devteam.agents.reviewer import reviewer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    always_read = _make_response("", [_make_tool_call("file_read", {"path": "main.py"})])

    with patch("devteam.agents.reviewer.call_llm_with_tools", return_value=always_read):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = reviewer_agent(state)

    assert result.get("error") is not None
    assert "最大步数" in result["error"]
