"""Tests for trace DB module."""
import time

from blueprint.utils.trace_db import TraceDB


def test_save_and_get_trace():
    """Should save and retrieve traces."""
    db = TraceDB(":memory:")
    db.save(
        project_id="test-proj",
        agent="developer",
        iteration=1,
        prompt="Build a calculator",
        response="I will create main.py",
        tools_called=[{"name": "file_write", "args": {"path": "main.py"}}],
        duration_ms=3500,
    )
    traces = db.get_traces("test-proj", agent="developer")
    assert len(traces) == 1
    assert traces[0]["agent"] == "developer"
    assert traces[0]["iteration"] == 1


def test_get_traces_filtered():
    """Should filter by agent and iteration."""
    db = TraceDB(":memory:")
    db.save(project_id="p1", agent="developer", iteration=1, prompt="a", response="b", tools_called=[], duration_ms=100)
    db.save(project_id="p1", agent="tester", iteration=1, prompt="c", response="d", tools_called=[], duration_ms=200)
    db.save(project_id="p1", agent="developer", iteration=2, prompt="e", response="f", tools_called=[], duration_ms=300)

    dev_traces = db.get_traces("p1", agent="developer")
    assert len(dev_traces) == 2

    iter1_traces = db.get_traces("p1", iteration=1)
    assert len(iter1_traces) == 2


def test_empty_traces():
    """Should return empty list for unknown project."""
    db = TraceDB(":memory:")
    traces = db.get_traces("nonexistent")
    assert traces == []
