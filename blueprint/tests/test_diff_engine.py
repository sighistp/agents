"""Tests for diff engine module."""
import json
import tempfile
from pathlib import Path

from blueprint.utils.diff_engine import DiffEngine


def test_save_snapshot():
    """Should save file snapshot for an iteration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("v1")
        (Path(tmpdir) / "utils.py").write_text("old")

        engine = DiffEngine(tmpdir)
        engine.save_snapshot(1)

        # Snapshots stored at parent/.snapshots/<project_name>/
        snap_dir = Path(tmpdir).parent / ".snapshots" / Path(tmpdir).name
        assert snap_dir.exists()
        snap_files = list(snap_dir.glob("iter_001*"))
        assert len(snap_files) == 1

        data = json.loads(snap_files[0].read_text(encoding="utf-8"))
        assert "main.py" in data
        assert data["main.py"] == "v1"

        # Cleanup
        import shutil
        shutil.rmtree(snap_dir, ignore_errors=True)


def test_compare_snapshots():
    """Should show diff between two iterations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = DiffEngine(tmpdir)

        (Path(tmpdir) / "main.py").write_text("line1\nline2\n")
        engine.save_snapshot(1)

        (Path(tmpdir) / "main.py").write_text("line1\nline3\n")
        (Path(tmpdir) / "new.py").write_text("new file")
        engine.save_snapshot(2)

        result = engine.compare(1, 2)
        assert result["files_changed"] >= 1
        assert result["total_additions"] >= 1


def test_list_snapshots():
    """Should list all snapshot iteration numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = DiffEngine(tmpdir)
        (Path(tmpdir) / "main.py").write_text("x")

        engine.save_snapshot(1)
        engine.save_snapshot(3)
        engine.save_snapshot(5)

        snapshots = engine.list_snapshots()
        assert snapshots == [1, 3, 5]


def test_compare_identical():
    """Comparing same snapshot should show no changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = DiffEngine(tmpdir)
        (Path(tmpdir) / "main.py").write_text("same")

        engine.save_snapshot(1)
        engine.save_snapshot(2)

        result = engine.compare(1, 2)
        assert result["files_changed"] == 0
