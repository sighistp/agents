"""Tests for Architect Agent module."""
import pytest


def test_architect_system_prompt_exists():
    """ARCHITECT_SYSTEM_PROMPT should be defined."""
    from blueprint.agents.architect import ARCHITECT_SYSTEM_PROMPT
    assert isinstance(ARCHITECT_SYSTEM_PROMPT, str)
    assert len(ARCHITECT_SYSTEM_PROMPT) > 0


def test_architect_system_prompt_contains_role():
    """Prompt should define the architect role."""
    from blueprint.agents.architect import ARCHITECT_SYSTEM_PROMPT
    assert "架构" in ARCHITECT_SYSTEM_PROMPT or "architect" in ARCHITECT_SYSTEM_PROMPT.lower()


def test_architect_system_prompt_contains_output_format():
    """Prompt should specify JSON output format."""
    from blueprint.agents.architect import ARCHITECT_SYSTEM_PROMPT
    assert "json" in ARCHITECT_SYSTEM_PROMPT.lower() or "JSON" in ARCHITECT_SYSTEM_PROMPT


def test_architect_critic_prompt_exists():
    """ARCHITECT_CRITIC_PROMPT should be defined for Proposer-Critic pattern."""
    from blueprint.agents.architect import ARCHITECT_CRITIC_PROMPT
    assert isinstance(ARCHITECT_CRITIC_PROMPT, str)
    assert len(ARCHITECT_CRITIC_PROMPT) > 0


def test_build_architect_prompt_basic():
    """build_architect_prompt should return a list of messages."""
    from blueprint.agents.architect import build_architect_prompt
    state = {
        "user_stories": [{"id": "US-001", "title": "Create todo"}],
        "features": [{"name": "Todo CRUD"}],
        "requirement": "Build a todo app",
    }
    messages = build_architect_prompt(state)
    assert isinstance(messages, list)
    assert len(messages) >= 2  # system + user


def test_build_architect_prompt_includes_system_prompt():
    """Messages should include the system prompt."""
    from blueprint.agents.architect import build_architect_prompt, ARCHITECT_SYSTEM_PROMPT
    state = {
        "user_stories": [{"id": "US-001", "title": "Create todo"}],
        "features": [],
        "requirement": "Build a todo app",
    }
    messages = build_architect_prompt(state)
    system_msgs = [m for m in messages if m.get("role") == "system"]
    assert any(ARCHITECT_SYSTEM_PROMPT[:50] in m.get("content", "") for m in system_msgs)


def test_build_architect_prompt_with_user_feedback():
    """Prompt should include user feedback when present."""
    from blueprint.agents.architect import build_architect_prompt
    state = {
        "user_stories": [{"id": "US-001", "title": "Create todo"}],
        "features": [],
        "requirement": "Build a todo app",
        "user_feedback": "Use React instead of vanilla JS",
    }
    messages = build_architect_prompt(state)
    user_msgs = [m for m in messages if m.get("role") == "user"]
    assert any("React" in m.get("content", "") for m in user_msgs)


@pytest.mark.asyncio
async def test_architect_agent_returns_correct_keys():
    """architect_agent should return state update with correct keys."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch, MagicMock

    mock_response = MagicMock()
    mock_response.content = '''
    {
        "architecture_description": "REST API with SQLite",
        "tech_stack": {"backend": "FastAPI", "database": "SQLite"},
        "modules": ["api", "models"],
        "api_definitions": [
            {"method": "GET", "path": "/api/todos", "description": "List todos"}
        ],
        "data_models": [
            {"name": "Todo", "fields": {"id": "int", "title": "str", "done": "bool"}}
        ]
    }
    '''

    with patch("blueprint.agents.architect.call_llm_async", return_value=mock_response.content):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    assert "architecture" in result
    assert "api_definitions" in result
    assert "data_models" in result
    assert "current_agent" in result


@pytest.mark.asyncio
async def test_architect_agent_sets_current_agent_to_developer():
    """architect_agent should set current_agent to 'developer'."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch

    mock_response = '''
    {
        "architecture_description": "REST API",
        "tech_stack": {"backend": "FastAPI"},
        "modules": ["api"],
        "api_definitions": [{"method": "GET", "path": "/api/todos", "description": "List"}],
        "data_models": [{"name": "Todo", "fields": {"id": "int"}}]
    }
    '''

    with patch("blueprint.agents.architect.call_llm_async", return_value=mock_response):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    assert result["current_agent"] == "developer"


@pytest.mark.asyncio
async def test_architect_agent_validates_output_schema():
    """architect_agent should validate output against ArchitectOutput schema."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch

    mock_response = '''
    {
        "architecture_description": "REST API",
        "tech_stack": {"backend": "FastAPI"},
        "modules": ["api"],
        "api_definitions": [{"method": "GET", "path": "/api/todos", "description": "List"}],
        "data_models": [{"name": "Todo", "fields": {"id": "int"}}]
    }
    '''

    with patch("blueprint.agents.architect.call_llm_async", return_value=mock_response):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    # Should be JSON serializable
    import json
    json.dumps(result["architecture"])
    json.dumps(result["api_definitions"])
    json.dumps(result["data_models"])


@pytest.mark.asyncio
async def test_architect_agent_calls_llm():
    """architect_agent should call LLM."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch, MagicMock

    mock_response = '''
    {
        "architecture_description": "REST API",
        "tech_stack": {"backend": "FastAPI"},
        "modules": ["api"],
        "api_definitions": [{"method": "GET", "path": "/api/todos", "description": "List"}],
        "data_models": [{"name": "Todo", "fields": {"id": "int"}}]
    }
    '''

    with patch("blueprint.agents.architect.call_llm_async", return_value=mock_response) as mock_llm:
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        await architect_agent(state)

    # With Proposer-Critic, call_llm is called multiple times
    mock_llm.assert_called()


@pytest.mark.asyncio
async def test_architect_agent_handles_invalid_json():
    """architect_agent should handle invalid JSON from LLM."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch

    with patch("blueprint.agents.architect.call_llm_async", return_value="not valid json"):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    assert "error" in result


@pytest.mark.asyncio
async def test_architect_agent_handles_empty_api_definitions():
    """architect_agent should handle empty api_definitions."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch

    mock_response = '''
    {
        "architecture_description": "REST API",
        "tech_stack": {"backend": "FastAPI"},
        "modules": ["api"],
        "api_definitions": [],
        "data_models": []
    }
    '''

    with patch("blueprint.agents.architect.call_llm_async", return_value=mock_response):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    # Should still return valid result (empty is allowed for architect)
    assert "architecture" in result or "error" in result


@pytest.mark.asyncio
async def test_architect_agent_handles_llm_exception():
    """architect_agent should handle LLM exceptions gracefully."""
    from blueprint.agents.architect import architect_agent
    from unittest.mock import patch

    with patch("blueprint.agents.architect.call_llm_async", side_effect=Exception("API Error")):
        state = {
            "user_stories": [{"id": "US-001", "title": "Create todo"}],
            "features": [],
            "requirement": "Build a todo app",
            "messages": [],
        }
        result = await architect_agent(state)

    assert "error" in result


def test_architect_agent_import():
    """architect_agent should be importable."""
    from blueprint.agents.architect import architect_agent
    assert callable(architect_agent)
