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


@pytest.mark.asyncio
async def test_developer_uses_tools():
    """Developer 应使用工具循环而非 JSON 输出"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "main.py", "content": "print(1)"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成"})]),
    ]

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "main.py"})
            result = await developer_agent(state)

    assert "files" in result
    assert "main.py" in result["files"]
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_developer_returns_key_decisions():
    """Developer done 工具的 key_decisions 应传入返回值"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成", "key_decisions": ["用Flask"]})]),
    ]

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "a.py"})
            result = await developer_agent(state)

    assert "key_decisions" in result
    assert "用Flask" in result["key_decisions"]


@pytest.mark.asyncio
async def test_developer_handles_no_tool_calls():
    """LLM 不调工具时应当作隐式完成"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})]),
        _make_response("我完成了"),  # 没有 tool_calls
    ]

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "a.py"})
            result = await developer_agent(state)

    assert "files" in result
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_developer_max_steps():
    """超过最大步数应返回错误（无文件写入时）"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    # LLM 只读文件不写文件，也不调 done → 真正的 max steps
    always_read = _make_response("", [_make_tool_call("file_read", {"path": "a.py"})])

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, return_value=always_read):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "x=1"})
            result = await developer_agent(state)

    assert result.get("error") is not None
    assert "最大步数" in result["error"]


@pytest.mark.asyncio
async def test_developer_implicit_done_with_files():
    """LLM 写了文件后下一轮无新写入，应视为隐式完成（不报错）"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    # 第1轮：写文件；第2轮：只执行代码（无新写入）→ 隐式完成
    write_resp = _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})])
    exec_resp = _make_response("", [_make_tool_call("execute_python", {"code": "print(1)"})])

    call_count = 0
    async def mock_llm(messages, tools):
        nonlocal call_count
        call_count += 1
        return write_resp if call_count == 1 else exec_resp

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=mock_llm):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "stdout": "1\n", "returncode": 0})
            result = await developer_agent(state)

    # files_written + 隐式 done = 成功，不应有 error
    assert result.get("error") is None
    assert result.get("files", {}).get("a.py") == "x=1"
    assert call_count == 2  # 只调了2轮LLM，不是10轮


@pytest.mark.asyncio
async def test_developer_handles_llm_error():
    """LLM 调用失败应返回错误"""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    with patch("devteam.agents.developer.call_llm_with_tools_async", new_callable=AsyncMock, side_effect=Exception("API Error")):
        result = await developer_agent(state)

    assert "error" in result
    assert "API Error" in result["error"]
