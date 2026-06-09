"""Tests for the project memory utility module."""

import pytest

from devteam.utils.memory import ProjectMemory


@pytest.fixture
def memory(tmp_path):
    """Provide a fresh ProjectMemory backed by a temporary database."""
    db_path = str(tmp_path / "test_memory.db")
    mem = ProjectMemory(db_path=db_path)
    yield mem
    mem.close()


# ── save_project Tests ───────────────────────────────────────────────────


def test_save_project(memory):
    """A saved project should be retrievable."""
    memory.save_project(
        project_id="proj-1",
        requirement="Build a todo app",
        status="created",
    )
    projects = memory.get_recent_projects(limit=10)
    assert len(projects) == 1
    assert projects[0]["project_id"] == "proj-1"
    assert projects[0]["requirement"] == "Build a todo app"
    assert projects[0]["status"] == "created"


def test_save_project_with_optional_fields(memory):
    """A project saved with user_stories and files should persist."""
    memory.save_project(
        project_id="proj-2",
        requirement="Build a chatbot",
        status="created",
        user_stories=[{"id": "US-1", "title": "Chat"}],
        files={"main.py": "print('hello')"},
    )
    projects = memory.get_recent_projects(limit=10)
    assert len(projects) == 1
    assert projects[0]["project_id"] == "proj-2"


# ── get_recent_projects Tests ────────────────────────────────────────────


def test_get_recent_projects_empty(memory):
    """Empty database should return an empty list."""
    assert memory.get_recent_projects() == []


def test_get_recent_projects_order(memory):
    """Projects should be returned in reverse insertion order (most recent first)."""
    memory.save_project("proj-a", "First project", "created")
    memory.save_project("proj-b", "Second project", "created")
    memory.save_project("proj-c", "Third project", "created")

    projects = memory.get_recent_projects(limit=10)
    assert len(projects) == 3
    assert projects[0]["project_id"] == "proj-c"
    assert projects[1]["project_id"] == "proj-b"
    assert projects[2]["project_id"] == "proj-a"


def test_get_recent_projects_limit(memory):
    """Limit should cap the number of results."""
    for i in range(5):
        memory.save_project(f"proj-{i}", f"Project {i}", "created")

    projects = memory.get_recent_projects(limit=3)
    assert len(projects) == 3


# ── update_status Tests ──────────────────────────────────────────────────


def test_update_status(memory):
    """Status update should change the latest entry for a project."""
    memory.save_project("proj-1", "Build a todo app", "created")
    memory.update_status("proj-1", "delivered")

    projects = memory.get_recent_projects(limit=10)
    assert len(projects) == 1
    assert projects[0]["status"] == "delivered"
