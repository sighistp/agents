"""Tests for deliver_node hook chain."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from blueprint.agents.graph import deliver_node


def _base_state(**overrides):
    state = {
        "project_id": "test-hook-123",
        "files": {"main.py": "print('hello')"},
        "requirement": "test requirement",
        "iteration": 1,
        "architecture": {},
        "user_stories": [],
        "features": [],
    }
    state.update(overrides)
    return state


def test_deliver_node_return_structure(tmp_path):
    """Verify return structure is unchanged after hooks."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    try:
        result = deliver_node(_base_state())
        assert result["status"] == "delivered"
        assert result["current_agent"] == "done"
        assert "files" in result
        assert "messages" in result
        assert result["files"] == _base_state()["files"]
    finally:
        settings.project_dir = old_val


def test_deliver_node_writes_files(tmp_path):
    """Verify files are actually written to disk."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    try:
        deliver_node(_base_state())
        project_dir = tmp_path / "test-hook-123"
        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "main.py").read_text() == "print('hello')"
    finally:
        settings.project_dir = old_val


def test_deliver_node_writes_meta(tmp_path):
    """Verify meta.json is written."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    try:
        deliver_node(_base_state(requirement="build a calculator"))
        meta_path = tmp_path / "test-hook-123" / "meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["requirement"] == "build a calculator"
    finally:
        settings.project_dir = old_val


def test_deliver_node_empty_files():
    """Empty files should return failed status."""
    state = _base_state(files={})
    result = deliver_node(state)
    assert result["status"] == "failed"


def test_deliver_node_invalid_project_id():
    """Invalid project_id should return failed."""
    state = _base_state(project_id="../../../etc/passwd")
    result = deliver_node(state)
    assert result["status"] == "failed"


def test_deliver_node_hooks_are_called(tmp_path):
    """Hooks should be called after file writing."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    hook_calls = []

    def mock_hook(state, project_dir):
        hook_calls.append(project_dir.name)

    # Temporarily add a hook
    from blueprint.agents import graph
    original_hooks = getattr(graph, '_post_deliver_hooks', [])
    graph._post_deliver_hooks = [mock_hook]
    try:
        deliver_node(_base_state())
        assert len(hook_calls) == 1
        assert hook_calls[0] == "test-hook-123"
    finally:
        graph._post_deliver_hooks = original_hooks
        settings.project_dir = old_val


def test_deliver_node_hook_failure_doesnt_break_delivery(tmp_path):
    """Hook failure should not prevent delivery."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)

    def failing_hook(state, project_dir):
        raise RuntimeError("hook exploded")

    from blueprint.agents import graph
    original_hooks = getattr(graph, '_post_deliver_hooks', [])
    graph._post_deliver_hooks = [failing_hook]
    try:
        result = deliver_node(_base_state())
        assert result["status"] == "delivered"  # Still delivered!
    finally:
        graph._post_deliver_hooks = original_hooks
        settings.project_dir = old_val


def test_deliver_node_webhook_hook(tmp_path):
    """Webhook hook should send notification when config exists."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)

    # Create webhook config
    data_dir = tmp_path.parent / "data"
    data_dir.mkdir(exist_ok=True)
    config_path = data_dir / "webhooks.json"
    config_path.write_text(json.dumps({
        "webhooks": [{"url": "http://example.com/hook", "events": ["*"], "secret": None}]
    }))

    from blueprint.agents import graph

    with patch("blueprint.utils.webhook.WebhookManager") as MockWM:
        mock_wm = MagicMock()
        MockWM.return_value = mock_wm
        mock_wm.notify = MagicMock()

        deliver_node(_base_state(project_id="webhook-test"))

        # WebhookManager should have been instantiated and notify called
        MockWM.assert_called()
        mock_wm.notify.assert_called()
        call_args = mock_wm.notify.call_args
        assert call_args[0][0] == "project.completed"
        assert call_args[0][1]["project_id"] == "webhook-test"

    settings.project_dir = old_val
