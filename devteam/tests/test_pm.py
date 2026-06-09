"""Tests for the PM (Product Manager) Agent module."""
import json
from unittest.mock import MagicMock, patch

import pytest

from devteam.agents.pm import pm_agent
from devteam.agents.state import ProjectState, create_initial_state


# ── Constants Tests ──────────────────────────────────────────────────────


def test_pm_system_prompt_exists():
    """PM_SYSTEM_PROMPT should be a non-empty string."""
    from devteam.agents.pm import PM_SYSTEM_PROMPT

    assert isinstance(PM_SYSTEM_PROMPT, str)
    assert len(PM_SYSTEM_PROMPT) > 100


def test_pm_system_prompt_contains_role():
    """PM_SYSTEM_PROMPT should define the PM role."""
    from devteam.agents.pm import PM_SYSTEM_PROMPT

    assert "产品经理" in PM_SYSTEM_PROMPT or "PM" in PM_SYSTEM_PROMPT


def test_pm_system_prompt_contains_output_format():
    """PM_SYSTEM_PROMPT should specify the JSON output format."""
    from devteam.agents.pm import PM_SYSTEM_PROMPT

    assert "user_stories" in PM_SYSTEM_PROMPT
    assert "features" in PM_SYSTEM_PROMPT


def test_pm_critic_prompt_exists():
    """PM_CRITIC_PROMPT should be a non-empty string."""
    from devteam.agents.pm import PM_CRITIC_PROMPT

    assert isinstance(PM_CRITIC_PROMPT, str)
    assert len(PM_CRITIC_PROMPT) > 50


def test_pm_critic_prompt_contains_review():
    """PM_CRITIC_PROMPT should instruct review of PM output."""
    from devteam.agents.pm import PM_CRITIC_PROMPT

    assert "审查" in PM_CRITIC_PROMPT or "review" in PM_CRITIC_PROMPT.lower()


# ── build_pm_prompt Tests ────────────────────────────────────────────────


def test_build_pm_prompt_basic():
    """build_pm_prompt should include the requirement in the user message."""
    from devteam.agents.pm import build_pm_prompt

    state = create_initial_state("test-1", "Build a todo app")
    messages = build_pm_prompt(state)

    # Should return a list of message dicts
    assert isinstance(messages, list)
    assert len(messages) >= 2  # system + user

    # First message should be system
    assert messages[0]["role"] == "system"

    # Should contain the requirement
    full_text = " ".join(m["content"] for m in messages)
    assert "Build a todo app" in full_text


def test_build_pm_prompt_includes_system_prompt():
    """build_pm_prompt should use PM_SYSTEM_PROMPT as the system message."""
    from devteam.agents.pm import PM_SYSTEM_PROMPT, build_pm_prompt

    state = create_initial_state("test-1", "Build a calculator")
    messages = build_pm_prompt(state)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == PM_SYSTEM_PROMPT


def test_build_pm_prompt_with_user_feedback():
    """build_pm_prompt should include user_feedback when present (rethink)."""
    from devteam.agents.pm import build_pm_prompt

    state = create_initial_state("test-1", "Build a todo app")
    state["user_feedback"] = "Please add user authentication stories"
    messages = build_pm_prompt(state)

    full_text = " ".join(m["content"] for m in messages)
    assert "user authentication" in full_text.lower() or "authentication stories" in full_text.lower()


def test_build_pm_prompt_without_user_feedback():
    """build_pm_prompt should work normally without user_feedback."""
    from devteam.agents.pm import build_pm_prompt

    state = create_initial_state("test-1", "Build a todo app")
    assert state.get("user_feedback") is None
    messages = build_pm_prompt(state)

    assert isinstance(messages, list)
    assert len(messages) >= 2


# ── pm_agent Normal Flow Tests ──────────────────────────────────────────


VALID_PM_RESPONSE = json.dumps({
    "user_stories": [
        {
            "id": "US-001",
            "title": "Create todo item",
            "description": "User can create a new todo item",
            "acceptance_criteria": [
                "Given a form, when user submits with title, then todo is created"
            ],
            "priority": "high"
        }
    ],
    "features": [
        {
            "name": "Todo CRUD",
            "description": "Basic todo CRUD operations",
            "priority": "high",
            "related_stories": ["US-001"]
        }
    ],
    "technical_constraints": ["Must use Python 3.12+"],
    "needs_clarification": False,
    "clarification_questions": []
})


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_returns_correct_keys(mock_call_llm):
    """pm_agent should return a dict with the expected state keys."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert "user_stories" in result
    assert "features" in result
    assert "current_agent" in result


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_sets_current_agent_to_architect(mock_call_llm):
    """pm_agent should set current_agent to 'architect' on success."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert result["current_agent"] == "architect"


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_validates_output_schema(mock_call_llm):
    """pm_agent should parse and validate the LLM output as PMOutput."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert len(result["user_stories"]) == 1
    assert result["user_stories"][0]["id"] == "US-001"
    assert len(result["features"]) == 1
    assert result["features"][0]["name"] == "Todo CRUD"


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_calls_llm(mock_call_llm):
    """pm_agent should call call_llm with messages."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    await pm_agent(state)

    # With Proposer-Critic, call_llm is called multiple times
    mock_call_llm.assert_called()
    call_args = mock_call_llm.call_args[0][0]
    assert isinstance(call_args, list)
    assert len(call_args) >= 2


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_includes_technical_constraints(mock_call_llm):
    """pm_agent should include technical_constraints in the result."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert "technical_constraints" in result
    assert "Must use Python 3.12+" in result["technical_constraints"]


# ── pm_agent Clarification Tests ────────────────────────────────────────


CLARIFICATION_RESPONSE = json.dumps({
    "user_stories": [
        {
            "id": "US-001",
            "title": "Create todo item",
            "description": "User can create a new todo item",
            "acceptance_criteria": [
                "Given a form, when user submits with title, then todo is created"
            ],
            "priority": "high"
        }
    ],
    "features": [],
    "technical_constraints": [],
    "needs_clarification": True,
    "clarification_questions": [
        "What database should be used?",
        "Is user authentication required?"
    ]
})


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_clarification_sets_needs_clarification(mock_call_llm):
    """pm_agent should detect needs_clarification from LLM response."""
    mock_call_llm.return_value = CLARIFICATION_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    # Should detect clarification is needed (interrupt will be called in graph context)
    assert result.get("needs_clarification") == True
    assert len(result.get("clarification_questions", [])) > 0


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_clarification_includes_questions(mock_call_llm):
    """pm_agent should include clarification questions in result."""
    mock_call_llm.return_value = CLARIFICATION_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    # Should include clarification questions
    assert "clarification_questions" in result
    assert len(result["clarification_questions"]) == 2


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_clarification_still_has_stories(mock_call_llm):
    """pm_agent should return user_stories even when clarification needed."""
    mock_call_llm.return_value = CLARIFICATION_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert len(result["user_stories"]) >= 1


# ── pm_agent Rethink (User Feedback) Tests ──────────────────────────────


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_with_user_feedback(mock_call_llm):
    """pm_agent should incorporate user_feedback into the prompt."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    state["user_feedback"] = "Add authentication stories"
    await pm_agent(state)

    # Check that the user feedback was included in the first call (proposer)
    first_call_args = mock_call_llm.call_args_list[0][0][0]
    full_text = " ".join(m["content"] for m in first_call_args)
    assert "authentication" in full_text.lower()


# ── pm_agent Error Handling Tests ────────────────────────────────────────


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_handles_invalid_json(mock_call_llm):
    """pm_agent should handle invalid JSON from LLM gracefully."""
    mock_call_llm.return_value = "This is not valid JSON at all"

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert "error" in result
    assert result["error"] is not None


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_handles_empty_user_stories(mock_call_llm):
    """pm_agent should handle LLM returning empty user_stories (schema violation)."""
    invalid_response = json.dumps({
        "user_stories": [],
        "features": [],
        "technical_constraints": [],
        "needs_clarification": False,
        "clarification_questions": []
    })
    mock_call_llm.return_value = invalid_response

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert "error" in result
    assert result["error"] is not None


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_handles_llm_exception(mock_call_llm):
    """pm_agent should handle LLM call raising an exception."""
    mock_call_llm.side_effect = RuntimeError("API connection failed")

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert "error" in result
    assert result["error"] is not None


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_handles_json_with_extra_text(mock_call_llm):
    """pm_agent should handle LLM response with markdown code fences around JSON."""
    wrapped_response = "```json\n" + VALID_PM_RESPONSE + "\n```"
    mock_call_llm.return_value = wrapped_response

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    # Should still parse successfully
    assert "user_stories" in result
    assert result["error"] is None if "error" in result else True
    assert len(result["user_stories"]) == 1


# ── pm_agent Edge Cases ─────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_multiple_user_stories(mock_call_llm):
    """pm_agent should handle multiple user stories."""
    multi_story_response = json.dumps({
        "user_stories": [
            {
                "id": "US-001",
                "title": "Create todo",
                "description": "User can create a todo",
                "acceptance_criteria": ["Can create a todo"],
                "priority": "high"
            },
            {
                "id": "US-002",
                "title": "Delete todo",
                "description": "User can delete a todo",
                "acceptance_criteria": ["Can delete a todo"],
                "priority": "medium"
            }
        ],
        "features": [
            {
                "name": "Todo CRUD",
                "description": "CRUD operations",
                "priority": "high",
                "related_stories": ["US-001", "US-002"]
            }
        ],
        "technical_constraints": [],
        "needs_clarification": False,
        "clarification_questions": []
    })
    mock_call_llm.return_value = multi_story_response

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    assert len(result["user_stories"]) == 2
    assert result["user_stories"][0]["id"] == "US-001"
    assert result["user_stories"][1]["id"] == "US-002"


@pytest.mark.asyncio
@patch("devteam.agents.pm.call_llm_async")
async def test_pm_agent_result_is_json_serializable(mock_call_llm):
    """pm_agent result values should be JSON-serializable (for LangGraph state)."""
    mock_call_llm.return_value = VALID_PM_RESPONSE

    state = create_initial_state("test-1", "Build a todo app")
    result = await pm_agent(state)

    # Should not raise
    json.dumps(result["user_stories"])
    json.dumps(result["features"])


def test_pm_agent_import():
    """pm_agent should be importable from devteam.agents.pm."""
    from devteam.agents.pm import pm_agent as imported_pm_agent

    assert callable(imported_pm_agent)
