"""Diff engine — save snapshots and compare iterations."""
import difflib
import gzip
import json
from pathlib import Path
from typing import Any


class DiffEngine:
    def __init__(self, project_dir: str, data_dir: str = None):
        self.project_dir = Path(project_dir)
        if data_dir:
            self.snapshots_dir = Path(data_dir) / "snapshots" / self.project_dir.name
        else:
            self.snapshots_dir = self.project_dir.parent / ".snapshots" / self.project_dir.name

    def save_snapshot(self, iteration: int):
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {}
        skip = {'.git', 'node_modules', '__pycache__', '.snapshots', '.venv', '_blueprint'}
        for f in self.project_dir.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                if not any(part in skip for part in f.parts):
                    try:
                        rel = str(f.relative_to(self.project_dir))
                        snapshot[rel] = f.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
        snap_file = self.snapshots_dir / f"iter_{iteration:03d}.json"
        data = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
        if len(data) > 10240:
            with gzip.open(str(snap_file) + ".gz", "wb") as f:
                f.write(data)
        else:
            snap_file.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    def compare(self, iter_a: int, iter_b: int) -> dict[str, Any]:
        snap_a = self._load_snapshot(iter_a)
        snap_b = self._load_snapshot(iter_b)
        all_files = set(snap_a.keys()) | set(snap_b.keys())
        diffs = {}
        total_add = 0
        total_del = 0

        for filepath in sorted(all_files):
            content_a = snap_a.get(filepath, "")
            content_b = snap_b.get(filepath, "")
            if content_a != content_b:
                diff_lines = list(difflib.unified_diff(
                    content_a.splitlines(keepends=True),
                    content_b.splitlines(keepends=True),
                    fromfile=f"iter_{iter_a}/{filepath}",
                    tofile=f"iter_{iter_b}/{filepath}",
                ))
                additions = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
                deletions = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
                total_add += additions
                total_del += deletions
                file_type = "modified" if filepath in snap_a and filepath in snap_b else (
                    "added" if filepath in snap_b else "deleted"
                )
                diffs[filepath] = {
                    "type": file_type,
                    "diff": "".join(diff_lines),
                    "additions": additions,
                    "deletions": deletions,
                }

        return {
            "iterations": [iter_a, iter_b],
            "files_changed": len(diffs),
            "total_additions": total_add,
            "total_deletions": total_del,
            "diffs": diffs,
        }

    def list_snapshots(self) -> list[int]:
        if not self.snapshots_dir.exists():
            return []
        results = []
        for f in self.snapshots_dir.glob("iter_*"):
            name = f.stem
            if f.suffix == ".gz":
                name = name[:-3]  # remove .gz from iter_001.json.gz
            try:
                results.append(int(name.split("_")[1]))
            except (IndexError, ValueError):
                pass
        return sorted(results)

    def _load_snapshot(self, iteration: int) -> dict[str, str]:
        snap_file = self.snapshots_dir / f"iter_{iteration:03d}.json"
        gz_file = snap_file.with_suffix(".json.gz")
        if gz_file.exists():
            with gzip.open(str(gz_file), "rb") as f:
                return json.loads(f.read().decode("utf-8"))
        if snap_file.exists():
            return json.loads(snap_file.read_text(encoding="utf-8"))
        return {}
