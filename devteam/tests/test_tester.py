"""Tests for Tester Agent module."""
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


def test_tester_system_prompt_exists():
    from devteam.agents.tester import TESTER_SYSTEM_PROMPT
    assert isinstance(TESTER_SYSTEM_PROMPT, str)
    assert len(TESTER_SYSTEM_PROMPT) > 0


def test_tester_import():
    from devteam.agents.tester import tester_agent
    assert callable(tester_agent)


@pytest.mark.asyncio
async def test_tester_uses_tools():
    """Tester 应使用工具循环"""
    from devteam.agents.tester import tester_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-test", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("execute_python", {"code": "print(1)"})]),
        _make_response("", [_make_tool_call("done", {"summary": "1 passed, 0 failed"})]),
    ]

    with patch("devteam.agents.tester.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"returncode": 0, "stdout": "1\n", "stderr": ""})
            result = await tester_agent(state)

    assert "test_passed" in result
    assert "messages" in result


def test_tester_only_has_read_and_execute_tools():
    """Tester 不应有 file_write 工具"""
    from devteam.agents.tools import TESTER_TOOLS
    names = [t["function"]["name"] for t in TESTER_TOOLS]
    assert "file_write" not in names
    assert "file_read" in names
    assert "execute_python" in names
    assert "done" in names


@pytest.mark.asyncio
async def test_tester_handles_llm_error():
    from devteam.agents.tester import tester_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-test", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    with patch("devteam.agents.tester.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=Exception("API Error")):
        result = await tester_agent(state)

    assert "error" in result
