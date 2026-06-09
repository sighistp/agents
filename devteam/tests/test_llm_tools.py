import pytest
from unittest.mock import MagicMock, patch


def test_call_llm_with_tools_exists():
    from devteam.utils.llm import call_llm_with_tools
    assert callable(call_llm_with_tools)


def test_call_llm_with_tools_binds_tools():
    from devteam.utils.llm import call_llm_with_tools

    mock_llm = MagicMock()
    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools
    mock_llm_with_tools.invoke.return_value = MagicMock(content="ok", tool_calls=[])

    with patch("devteam.utils.llm._get_llm", return_value=mock_llm):
        result = call_llm_with_tools([{"role": "user", "content": "test"}], [{"type": "function", "function": {"name": "test_tool"}}])

    mock_llm.bind_tools.assert_called_once()
    mock_llm_with_tools.invoke.assert_called_once()
