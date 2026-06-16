"""Tests for step timeout in agents."""
import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_developer_step_timeout():
    """Developer should timeout if LLM call takes too long."""
    from blueprint.agents.developer import developer_agent

    call_count = 0

    async def slow_then_ok(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call hangs (simulated by raising TimeoutError after short delay)
            raise asyncio.TimeoutError("LLM call timed out after 60s")
        # Second call should not happen
        resp = MagicMock()
        resp.content = "done"
        resp.tool_calls = []
        return resp

    state = {
        "project_id": "timeout-test",
        "requirement": "test",
        "files": {"main.py": "x=1"},
        "project_dir": ".",
        "iteration": 0,
        "user_stories": [],
        "architecture": {},
        "api_definitions": [],
        "data_models": [],
    }

    with patch("blueprint.agents.developer.call_llm_with_tools_async", slow_then_ok):
        result = await developer_agent(state)
        assert "error" in result
        assert "超时" in result["error"]
