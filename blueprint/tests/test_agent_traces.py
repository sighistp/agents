"""Tests that developer, tester, and reviewer agents record traces via TraceDB."""
import json
from unittest.mock import patch, AsyncMock, MagicMock


def _base_state(**overrides):
    state = {
        "project_id": "proj-123",
        "iteration": 0,
        "requirement": "test requirement",
        "files": {"main.py": "print('hello')"},
        "project_dir": "/tmp/fake",
        "user_stories": [],
    }
    state.update(overrides)
    return state


# ── Developer ────────────────────────────────────────────────────────────────

@patch("blueprint.agents.developer.TraceDB")
@patch("blueprint.agents.developer.call_llm_with_tools_async")
def test_developer_records_trace(mock_llm, mock_trace_cls):
    from blueprint.agents.developer import developer_agent

    # LLM returns no tool calls → implicit done, but no files written → error path
    mock_resp = MagicMock()
    mock_resp.content = "done"
    mock_resp.tool_calls = []
    mock_llm = AsyncMock(return_value=mock_resp)

    # Patch call_llm at module level
    with patch("blueprint.agents.developer.call_llm_with_tools_async", mock_llm), \
         patch("blueprint.agents.developer.TraceDB") as mock_cls:
        mock_db = MagicMock()
        mock_cls.return_value = mock_db

        import asyncio
        state = _base_state(files={"main.py": "x=1"})
        result = asyncio.run(developer_agent(state))

        # TraceDB.save should have been called at least once
        assert mock_db.save.called, "TraceDB.save was not called by developer_agent"
        call_kwargs = mock_db.save.call_args
        assert call_kwargs[1]["agent"] == "developer" if call_kwargs[1] else call_kwargs[0][1] == "developer"


# ── Tester ───────────────────────────────────────────────────────────────────

@patch("blueprint.agents.tester.TraceDB")
@patch("blueprint.agents.tester.call_llm_with_tools_async")
def test_tester_records_trace(mock_llm, mock_trace_cls):
    from blueprint.agents.tester import tester_agent

    mock_resp = MagicMock()
    mock_resp.content = "testing complete"
    mock_resp.tool_calls = []
    mock_llm = AsyncMock(return_value=mock_resp)

    with patch("blueprint.agents.tester.call_llm_with_tools_async", mock_llm), \
         patch("blueprint.agents.tester.TraceDB") as mock_cls:
        mock_db = MagicMock()
        mock_cls.return_value = mock_db

        import asyncio
        state = _base_state()
        result = asyncio.run(tester_agent(state))

        assert mock_db.save.called, "TraceDB.save was not called by tester_agent"
        call_kwargs = mock_db.save.call_args
        assert call_kwargs[1]["agent"] == "tester" if call_kwargs[1] else call_kwargs[0][1] == "tester"


# ── Reviewer ─────────────────────────────────────────────────────────────────

@patch("blueprint.agents.reviewer.TraceDB")
@patch("blueprint.agents.reviewer.call_llm_with_tools_async")
def test_reviewer_records_trace(mock_llm, mock_trace_cls):
    from blueprint.agents.reviewer import reviewer_agent

    mock_resp = MagicMock()
    mock_resp.content = "review complete"
    mock_resp.tool_calls = []
    mock_llm = AsyncMock(return_value=mock_resp)

    with patch("blueprint.agents.reviewer.call_llm_with_tools_async", mock_llm), \
         patch("blueprint.agents.reviewer.TraceDB") as mock_cls:
        mock_db = MagicMock()
        mock_cls.return_value = mock_db

        import asyncio
        state = _base_state()
        result = asyncio.run(reviewer_agent(state))

        assert mock_db.save.called, "TraceDB.save was not called by reviewer_agent"
        call_kwargs = mock_db.save.call_args
        assert call_kwargs[1]["agent"] == "reviewer" if call_kwargs[1] else call_kwargs[0][1] == "reviewer"
