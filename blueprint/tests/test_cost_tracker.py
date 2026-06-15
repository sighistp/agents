import json
from unittest.mock import MagicMock
from blueprint.utils.cost_tracker import CostTracker

def test_record_cost_basic():
    tracker = CostTracker()
    response = MagicMock()
    response.usage_metadata = {"input_tokens": 1000, "output_tokens": 500}
    tracker.record_cost(response, project_id="test-proj")
    data = tracker.get_cost("test-proj")
    assert data["total_calls"] == 1
    assert data["total_input_tokens"] == 1000
    assert data["total_output_tokens"] == 500
    assert data["estimated_cost_usd"] > 0

def test_record_cost_accumulates():
    tracker = CostTracker()
    for _ in range(3):
        response = MagicMock()
        response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
        tracker.record_cost(response, project_id="proj-1")
    data = tracker.get_cost("proj-1")
    assert data["total_calls"] == 3
    assert data["total_input_tokens"] == 300

def test_record_cost_no_project_id():
    tracker = CostTracker()
    response = MagicMock()
    response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    tracker.record_cost(response, project_id="")
    assert tracker.get_cost("") == {}

def test_record_cost_no_usage():
    tracker = CostTracker()
    response = MagicMock()
    response.usage_metadata = None
    tracker.record_cost(response, project_id="proj-1")
    assert tracker.get_cost("proj-1") == {}

def test_record_cost_exception_safe():
    tracker = CostTracker()
    tracker.record_cost(None, project_id="proj-1")
    assert tracker.get_cost("proj-1") == {}

def test_project_isolation():
    tracker = CostTracker()
    r1 = MagicMock()
    r1.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    r2 = MagicMock()
    r2.usage_metadata = {"input_tokens": 200, "output_tokens": 100}
    tracker.record_cost(r1, project_id="a")
    tracker.record_cost(r2, project_id="b")
    assert tracker.get_cost("a")["total_input_tokens"] == 100
    assert tracker.get_cost("b")["total_input_tokens"] == 200