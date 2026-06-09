"""SQLite-backed user database for DevTeam.

Adapted from RAGv3 user_db system.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any, Optional

from devteam.api.auth import hash_password, verify_password

# Module-level singleton
_user_db: Optional["UserDB"] = None
_db_lock = threading.Lock()


def get_user_db() -> "UserDB":
    """Return the global UserDB singleton, creating it if needed."""
    global _user_db
    if _user_db is None:
        with _db_lock:
            if _user_db is None:
                db_path = os.environ.get(
                    "DEVTEAM_AUTH_DB",
                    os.path.join(os.path.dirname(__file__), "..", "devteam_users.db"),
                )
                _user_db = UserDB(db_path)
    return _user_db


class UserDB:
    """Thread-safe SQLite database for user management."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    username        TEXT    NOT NULL UNIQUE,
                    password_hash   TEXT    NOT NULL,
                    created_at      REAL    NOT NULL DEFAULT (strftime('%s','now'))
                );
                """
            )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def register_user(self, username: str, password: str) -> int:
        """Create a new user. Raises ValueError if the username is taken."""
        hashed = hash_password(password)
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, hashed),
                )
                self._conn.commit()
                return cur.lastrowid  # type: ignore[return-value]
            except sqlite3.IntegrityError:
                raise ValueError("Username already taken")

    def login_user(self, username: str, password: str) -> Optional[dict[str, Any]]:
        """Authenticate user. Returns user dict on success, None on failure."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"]}

    def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        """Return user dict by id, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "username": row["username"]}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()
