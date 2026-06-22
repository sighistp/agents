"""Project memory layer using SQLite.

Three tables:
- project_snapshots: project metadata and current state
- agent_executions: structured Agent execution records (no raw LLM output)
- project_messages: chat messages for frontend restore
"""
import json
import os
import sqlite3
import threading
from pathlib import Path

# M1: Support environment variable for DB path
_DB_DIR = Path(os.environ.get("BLUEPRINT_DATA_DIR",
                              str(Path(__file__).parent.parent / "data")))
_DB_PATH = _DB_DIR / "memory.db"

# M4: Constants for query limits
_MAX_CONTEXT_ROWS = 6
_CONTEXT_LOOKBACK = 2
_MAX_RESTORE_MESSAGES = 200

# C1: Allowed columns for snapshot save_snapshot
_SNAPSHOT_COLUMNS = {
    "requirement", "current_step", "iteration", "files_summary",
    "status", "last_heartbeat", "created_at", "updated_at"
}


class ProjectMemory:
    """SQLite-backed project memory for agent context and state persistence."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            _DB_DIR.mkdir(parents=True, exist_ok=True)
            db_path = str(_DB_PATH)
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local connection (safe for multi-threaded access)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS project_snapshots (
                project_id TEXT PRIMARY KEY,
                requirement TEXT,
                current_step TEXT DEFAULT 'pm',
                iteration INTEGER DEFAULT 0,
                files_summary TEXT,
                status TEXT DEFAULT 'active',
                last_heartbeat TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                input_summary TEXT,
                tool_calls TEXT,
                result_summary TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_exec ON agent_executions(project_id, agent_name, iteration);

            CREATE TABLE IF NOT EXISTS project_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                role TEXT NOT NULL,
                name TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_msg ON project_messages(project_id);

            CREATE TABLE IF NOT EXISTS agent_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                messages TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conv ON agent_conversations(project_id, agent_name, iteration);
        """)
        conn.commit()
        # Migration: add last_heartbeat column if missing
        try:
            conn.execute("ALTER TABLE project_snapshots ADD COLUMN last_heartbeat TIMESTAMP")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.close()

    # ── Snapshot Operations ─────────────────────────────────────────────

    def save_snapshot(self, project_id: str, **kwargs):
        """Create or update a project snapshot.

        Only accepts whitelisted column names (C1 fix).
        """
        # C1: Whitelist validation — column names come from _SNAPSHOT_COLUMNS,
        # values are parameterized (?). This is safe because:
        # 1. Only whitelisted column names are allowed
        # 2. Values use parameterized queries (? placeholders)
        # 3. SQLite doesn't support parameterized column names, so dynamic SQL is necessary
        invalid = set(kwargs.keys()) - _SNAPSHOT_COLUMNS
        if invalid:
            raise ValueError(f"Invalid snapshot columns: {invalid}")

        conn = self._get_conn()
        # Atomic transaction
        with conn:
            existing = conn.execute(
                "SELECT project_id FROM project_snapshots WHERE project_id = ?",
                (project_id,)
            ).fetchone()

            if existing:
                sets = ", ".join(f"{k} = ?" for k in kwargs)
                conn.execute(
                    f"UPDATE project_snapshots SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE project_id = ?",
                    (*kwargs.values(), project_id)
                )
            else:
                kwargs["project_id"] = project_id
                cols = ", ".join(kwargs.keys())
                placeholders = ", ".join(["?"] * len(kwargs))
                conn.execute(
                    f"INSERT INTO project_snapshots ({cols}) VALUES ({placeholders})",
                    tuple(kwargs.values())
                )

    def get_snapshot(self, project_id: str) -> dict | None:
        """Get a project snapshot by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM project_snapshots WHERE project_id = ?", (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_heartbeat(self, project_id: str):
        """Update the heartbeat timestamp to signal the graph is alive."""
        conn = self._get_conn()
        with conn:
            conn.execute(
                "UPDATE project_snapshots SET last_heartbeat = CURRENT_TIMESTAMP WHERE project_id = ?",
                (project_id,)
            )

    # ── Message Operations ──────────────────────────────────────────────

    def save_message(self, project_id: str, role: str, name: str, content: str):
        """Save a chat message."""
        conn = self._get_conn()
        with conn:
            conn.execute(
                "INSERT INTO project_messages (project_id, role, name, content) VALUES (?, ?, ?, ?)",
                (project_id, role, name, content[:5000])  # I1: Limit content length
            )

    def get_messages(self, project_id: str, limit: int = _MAX_RESTORE_MESSAGES) -> list[dict]:
        """Get messages for a project, in order.

        I1: Limited to _MAX_RESTORE_MESSAGES to prevent memory explosion.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, name, content, created_at FROM project_messages "
            "WHERE project_id = ? ORDER BY id DESC LIMIT ?",
            (project_id, limit)
        ).fetchall()
        # Reverse to get chronological order
        return [dict(r) for r in reversed(rows)]

    # ── Execution Operations ────────────────────────────────────────────

    def save_execution(self, project_id: str, agent_name: str, iteration: int,
                       input_summary: str = "", tool_calls=None,
                       result_summary: str = "", status: str = "success"):
        """Save an agent execution record."""
        # Normalize tool_calls: accept list, string, or None
        if tool_calls is not None:
            if isinstance(tool_calls, str):
                tc_json = tool_calls  # already a JSON string
            else:
                tc_json = json.dumps(tool_calls, ensure_ascii=False)
        else:
            tc_json = None
        conn = self._get_conn()
        with conn:
            conn.execute(
                """INSERT INTO agent_executions
                   (project_id, agent_name, iteration, input_summary,
                    tool_calls, result_summary, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, agent_name, iteration, input_summary[:2000],
                 tc_json, result_summary[:2000], status)
            )

    def get_executions(self, project_id: str) -> list[dict]:
        """Get all executions for a project, ordered by created_at ASC."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT agent_name, iteration, result_summary, tool_calls,
                      status, created_at
               FROM agent_executions
               WHERE project_id = ?
               ORDER BY created_at ASC""",
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_developer_context(self, project_id: str, current_iteration: int) -> str:
        """Build context summary for Developer from recent executions.

        Returns a markdown string with the last 2 iterations of results
        from all agents, so Developer knows what was tried before.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT agent_name, iteration, result_summary, status
               FROM agent_executions
               WHERE project_id = ? AND iteration >= ?
               ORDER BY iteration DESC, agent_name
               LIMIT ?""",
            (project_id, max(0, current_iteration - _CONTEXT_LOOKBACK), _MAX_CONTEXT_ROWS)
        ).fetchall()

        if not rows:
            return ""

        lines = ["## 之前的尝试："]
        for row in rows:
            r = dict(row)
            icon = "✅" if r["status"] == "success" else "❌"
            lines.append(
                f"- {icon} {r['agent_name']}（第{r['iteration']}轮）: {r['result_summary']}"
            )
        return "\n".join(lines)

    # ── Conversation Operations ──────────────────────────────────────────

    def save_conversation(self, project_id: str, agent_name: str,
                          iteration: int, messages_list: list):
        """Save a full agent conversation.

        Args:
            project_id: Project identifier.
            agent_name: Agent name (e.g. "developer").
            iteration: Iteration number.
            messages_list: List of message dicts, e.g.
                [{"role": "assistant", "content": "..."}, ...]
        """
        conn = self._get_conn()
        with conn:
            conn.execute(
                """INSERT INTO agent_conversations
                   (project_id, agent_name, iteration, messages)
                   VALUES (?, ?, ?, ?)""",
                (project_id, agent_name, iteration,
                 json.dumps(messages_list, ensure_ascii=False))
            )

    def get_conversations(self, project_id: str) -> list[dict]:
        """Get all conversations for a project, ordered by created_at ASC."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT agent_name, iteration, messages, created_at
               FROM agent_conversations
               WHERE project_id = ?
               ORDER BY created_at ASC""",
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Cleanup ─────────────────────────────────────────────────────────

    def cleanup_old_projects(self, days: int = 30):
        """Delete data for projects older than N days."""
        conn = self._get_conn()
        with conn:
            conn.execute(
                "DELETE FROM project_snapshots WHERE created_at < datetime('now', ?)",
                (f"-{days} days",)
            )
            conn.execute(
                "DELETE FROM agent_executions "
                "WHERE project_id NOT IN (SELECT project_id FROM project_snapshots)"
            )
            conn.execute(
                "DELETE FROM project_messages "
                "WHERE project_id NOT IN (SELECT project_id FROM project_snapshots)"
            )
            conn.execute(
                "DELETE FROM agent_conversations "
                "WHERE project_id NOT IN (SELECT project_id FROM project_snapshots)"
            )

    # ── Backward Compatibility ─────────────────────────────────────────

    def save_project(self, project_id: str, requirement: str, status: str,
                     user_stories: list = None, files: dict = None):
        """Backward-compatible project save."""
        self.save_snapshot(project_id, requirement=requirement, status=status)
        if user_stories:
            self.save_message(project_id, "assistant", "pm",
                              f"用户故事: {json.dumps(user_stories, ensure_ascii=False)}")
        if files:
            self.save_message(project_id, "assistant", "developer",
                              f"生成文件: {', '.join(files.keys())}")

    def update_status(self, project_id: str, status: str):
        """Backward-compatible status update."""
        self.save_snapshot(project_id, status=status)

    def get_recent_projects(self, limit: int = 10) -> list:
        """Backward-compatible project list."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT project_id, requirement, status, created_at "
            "FROM project_snapshots ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """Close all thread-local connections."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# ── Module-level singleton ──────────────────────────────────────────────────

_memory = None
_memory_lock = threading.Lock()


def get_memory() -> ProjectMemory:
    """Get the global ProjectMemory singleton (thread-safe)."""
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                _memory = ProjectMemory()
    return _memory