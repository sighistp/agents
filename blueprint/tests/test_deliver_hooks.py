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

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)

        deliver_node(_base_state(project_id="webhook-test"))

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://example.com/hook"

    settings.project_dir = old_val


# ── P2.1: Hook parallel execution ──────────────────────────────────────────

import pytest


@pytest.mark.asyncio
async def test_hooks_run_in_parallel():
    """P2.1: Independent hooks should run concurrently, not serially."""
    import asyncio
    import time

    call_log = []

    async def hook_a():
        call_log.append(("a", "start", time.monotonic()))
        await asyncio.sleep(0.1)
        call_log.append(("a", "end", time.monotonic()))

    async def hook_b():
        call_log.append(("b", "start", time.monotonic()))
        await asyncio.sleep(0.1)
        call_log.append(("b", "end", time.monotonic()))

    start = time.monotonic()
    await asyncio.gather(hook_a(), hook_b())
    elapsed = time.monotonic() - start

    # If parallel, total ~0.1s. If serial, ~0.2s
    assert elapsed < 0.15, f"Hooks ran serially ({elapsed:.2f}s), expected parallel"


@pytest.mark.asyncio
async def test_parallel_hooks_with_exception():
    """P2.1: asyncio.gather with return_exceptions=True should not raise on hook failure."""
    import asyncio

    async def good_hook():
        await asyncio.sleep(0.01)
        return "ok"

    async def bad_hook():
        await asyncio.sleep(0.01)
        raise RuntimeError("hook exploded")

    # Should not raise — return_exceptions=True catches it
    results = await asyncio.gather(good_hook(), bad_hook(), return_exceptions=True)
    assert results[0] == "ok"
    assert isinstance(results[1], RuntimeError)


@pytest.mark.asyncio
async def test_run_post_deliver_hooks_uses_parallel_execution(tmp_path):
    """P2.1: _run_post_deliver_hooks should run independent hooks concurrently."""
    import asyncio
    import time
    from blueprint.agents import graph

    call_log = []

    async def slow_hook_a(state, project_dir):
        call_log.append(("a", "start"))
        await asyncio.sleep(0.1)
        call_log.append(("a", "end"))

    async def slow_hook_b(state, project_dir):
        call_log.append(("b", "start"))
        await asyncio.sleep(0.1)
        call_log.append(("b", "end"))

    async def slow_hook_c(state, project_dir):
        call_log.append(("c", "start"))
        await asyncio.sleep(0.1)
        call_log.append(("c", "end"))

    original_hooks = graph._post_deliver_hooks
    graph._post_deliver_hooks = [slow_hook_a, slow_hook_b, slow_hook_c]
    try:
        start = time.monotonic()
        result = await graph._run_post_deliver_hooks({}, tmp_path)
        elapsed = time.monotonic() - start

        # If parallel: ~0.1s. If serial: ~0.3s
        assert elapsed < 0.2, f"Hooks ran serially ({elapsed:.2f}s), expected parallel execution"
        assert result is None  # Function should return None
    finally:
        graph._post_deliver_hooks = original_hooks
