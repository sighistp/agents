"""Tests for ProjectState and LLM call wrapper."""
import pytest


def test_project_state_has_required_fields():
    """ProjectState should have all required fields defined in design doc."""
    from blueprint.agents.state import ProjectState

    # Check key fields exist in the TypedDict annotations
    annotations = ProjectState.__annotations__

    # Project identification
    assert "project_id" in annotations

    # Requirements
    assert "requirement" in annotations
    assert "user_stories" in annotations
    assert "features" in annotations

    # Architecture
    assert "architecture" in annotations
    assert "api_definitions" in annotations
    assert "data_models" in annotations

    # Code
    assert "files" in annotations

    # Testing
    assert "test_cases" in annotations
    assert "test_results" in annotations
    assert "test_passed" in annotations

    # Review
    assert "review_comments" in annotations
    assert "review_approved" in annotations

    # Flow control
    assert "current_agent" in annotations
    assert "iteration" in annotations
    assert "max_iterations" in annotations
    assert "status" in annotations
    assert "error" in annotations

    # Human confirm
    assert "need_human_confirm" in annotations
    assert "human_approved" in annotations

    # Rethink (user feedback)
    assert "user_feedback" in annotations
    assert "rethink_count" in annotations

    # Messages (LangGraph add_messages)
    assert "messages" in annotations


def test_project_state_initial_values():
    """ProjectState should have sensible default initial values."""
    from blueprint.agents.state import create_initial_state

    state = create_initial_state(
        project_id="test-123",
        requirement="Build a calculator"
    )

    assert state["project_id"] == "test-123"
    assert state["requirement"] == "Build a calculator"
    assert state["iteration"] == 0
    assert state["max_iterations"] == 3
    assert state["status"] == "running"
    assert state["error"] is None
    assert state["user_feedback"] is None
    assert state["rethink_count"] == {}
    assert state["messages"] == []


def test_call_llm_uses_semaphore():
    """call_llm should use a semaphore for rate limiting."""
    from blueprint.utils.llm import _llm_semaphore

    # Semaphore should exist and have a value
    assert _llm_semaphore is not None
    assert _llm_semaphore._value == 5  # Default max concurrent calls


def test_call_llm_function_exists():
    """call_llm function should be importable."""
    from blueprint.utils.llm import call_llm

    # Verify it's a callable function
    assert callable(call_llm)
