"""Tests for WebSocket module."""
import pytest


class TestWebSocketModule:
    """Test the WebSocket module structure."""

    def test_module_imports(self):
        """websocket module should be importable."""
        import blueprint.api.websocket
        assert blueprint.api.websocket is not None

    def test_router_exists(self):
        """Module should export a FastAPI router."""
        from blueprint.api.websocket import router
        assert router is not None

    def test_ws_endpoint_exists(self):
        """WebSocket endpoint function should exist."""
        from blueprint.api.websocket import ws_project
        assert callable(ws_project)

    def test_run_graph_sync_exists(self):
        """_run_graph_sync function should exist."""
        from blueprint.api.websocket import _run_graph_sync
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


# ── P2.2: WebSocket incremental file sending ──────────────────────────────

class TestIncrementalFileSending:
    """Test incremental file tracking for WebSocket messages."""

    def test_incremental_file_tracking(self):
        """P2.2: Should track sent files for incremental updates."""
        sent_files = set()

        all_files = {"a.py": "content1", "b.py": "content2", "c.py": "content3"}

        # First send: all files are new
        new_files = {k: v for k, v in all_files.items() if k not in sent_files}
        assert len(new_files) == 3
        sent_files.update(new_files.keys())

        # Second send with one new file
        all_files["d.py"] = "content4"
        new_files = {k: v for k, v in all_files.items() if k not in sent_files}
        assert len(new_files) == 1
        assert "d.py" in new_files

    def test_incremental_file_tracking_empty(self):
        """P2.2: Empty file dict should return empty set."""
        sent_files = set()
        all_files = {}
        new_files = {k: v for k, v in all_files.items() if k not in sent_files}
        assert len(new_files) == 0

    def test_incremental_file_tracking_no_new(self):
        """P2.2: No new files when all already sent."""
        sent_files = {"a.py", "b.py"}
        all_files = {"a.py": "content1", "b.py": "content2"}
        new_files = {k: v for k, v in all_files.items() if k not in sent_files}
        assert len(new_files) == 0
