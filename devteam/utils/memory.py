"""Project history memory - adapted from RAGv3 memory.py"""

import json
import sqlite3
import threading
from pathlib import Path

# Default DB path: devteam/data/devteam_memory.db
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_DB_PATH = str(_DEFAULT_DB_DIR / "devteam_memory.db")


class ProjectMemory:
    """Store project history and conversation context."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            _DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
            db_path = _DEFAULT_DB_PATH
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS project_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                requirement TEXT,
                status TEXT,
                user_stories TEXT,
                files TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()

    def save_project(
        self,
        project_id: str,
        requirement: str,
        status: str,
        user_stories: list = None,
        files: dict = None,
    ) -> None:
        """Save project to history."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO project_history"
                " (project_id, requirement, status, user_stories, files)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    project_id,
                    requirement,
                    status,
                    json.dumps(user_stories or []),
                    json.dumps(files or {}),
                ),
            )
            self._conn.commit()

    def update_status(self, project_id: str, status: str) -> None:
        """Update the latest status entry for a project."""
        with self._lock:
            self._conn.execute(
                "UPDATE project_history SET status = ?"
                " WHERE id = (SELECT id FROM project_history"
                " WHERE project_id = ? ORDER BY id DESC LIMIT 1)",
                (status, project_id),
            )
            self._conn.commit()

    def get_recent_projects(self, limit: int = 10) -> list:
        """Get recent projects."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT project_id, requirement, status, created_at"
                " FROM project_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "project_id": r[0],
                "requirement": r[1],
                "status": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
