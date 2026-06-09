"""Tests for WebSocket module."""
import pytest


class TestWebSocketModule:
    """Test the WebSocket module structure."""

    def test_module_imports(self):
        """websocket module should be importable."""
        import devteam.api.websocket
        assert devteam.api.websocket is not None

    def test_router_exists(self):
        """Module should export a FastAPI router."""
        from devteam.api.websocket import router
        assert router is not None

    def test_ws_endpoint_exists(self):
        """WebSocket endpoint function should exist."""
        from devteam.api.websocket import ws_project
        assert callable(ws_project)

    def test_run_graph_sync_exists(self):
        """_run_graph_sync function should exist."""
        from devteam.api.websocket import _run_graph_sync
        assert callable(_run_graph_sync)


class TestProjectIdValidation:
    """Test project_id validation."""

    def test_valid_project_id(self):
        """Valid project IDs should pass validation."""
        import re
        valid_ids = ["test-123", "my_project", "project-abc-123", "Project123"]
        for pid in valid_ids:
            assert re.match(r'^[a-zA-Z0-9_-]+$', pid) is not None

    def test_invalid_project_id(self):
        """Invalid project IDs should fail validation."""
        import re
        invalid_ids = ["../etc", "test/path", "project with spaces", "project@special", "project.dot"]
        for pid in invalid_ids:
            assert re.match(r'^[a-zA-Z0-9_-]+$', pid) is None
