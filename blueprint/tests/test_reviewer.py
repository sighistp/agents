"""Tests for Reviewer Agent module."""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


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


def test_reviewer_system_prompt_exists():
    from blueprint.agents.reviewer import REVIEWER_SYSTEM_PROMPT
    assert isinstance(REVIEWER_SYSTEM_PROMPT, str)
    assert len(REVIEWER_SYSTEM_PROMPT) > 0


def test_reviewer_system_prompt_contains_role():
    from blueprint.agents.reviewer import REVIEWER_SYSTEM_PROMPT
    assert "审查" in REVIEWER_SYSTEM_PROMPT


def test_reviewer_agent_import():
    from blueprint.agents.reviewer import reviewer_agent
    assert callable(reviewer_agent)


@pytest.mark.asyncio
async def test_reviewer_uses_tools():
    from blueprint.agents.reviewer import reviewer_agent
    from blueprint.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("", [_make_tool_call("done", {"summary": "代码质量良好，无critical问题"})]),
    ]

    with patch("blueprint.agents.reviewer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = await reviewer_agent(state)

    assert "review_approved" in result
    assert "messages" in result


def test_reviewer_only_has_read_tool():
    from blueprint.agents.tools import REVIEWER_TOOLS
    names = [t["function"]["name"] for t in REVIEWER_TOOLS]
    assert "file_write" not in names
    assert "execute_python" not in names
    assert "file_read" in names
    assert "done" in names


@pytest.mark.asyncio
async def test_reviewer_handles_no_tool_calls():
    """LLM 不调工具时应当作隐式完成"""
    from blueprint.agents.reviewer import reviewer_agent
    from blueprint.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("审查通过，代码质量良好"),
    ]

    with patch("blueprint.agents.reviewer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = await reviewer_agent(state)

    assert "review_approved" in result
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_reviewer_max_steps():
    """超过最大步数应返回错误"""
    from blueprint.agents.reviewer import reviewer_agent
    from blueprint.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    always_read = _make_response("", [_make_tool_call("file_read", {"path": "main.py"})])

    with patch("blueprint.agents.reviewer.call_llm_with_tools_async", new_callable=AsyncMock, return_value=always_read):
        with patch("blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = await reviewer_agent(state)

    assert result.get("error") is not None
    assert "最大步数" in result["error"]
