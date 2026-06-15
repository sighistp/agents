"""Agent trace DB — stores LLM input/output/tool calls per agent execution."""
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class TraceDB:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "traces.db")
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                prompt TEXT,
                response TEXT,
                tools_called TEXT,
                duration_ms INTEGER,
                created_at REAL DEFAULT (strftime('%s','now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_proj ON agent_traces(project_id, agent)")
        conn.commit()

    def save(self, project_id: str, agent: str, iteration: int,
             prompt: str, response: str, tools_called: list[dict], duration_ms: int):
        """Save an agent trace."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO agent_traces (project_id, agent, iteration, prompt, response, tools_called, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, agent, iteration, prompt[:5000], response[:5000],
             json.dumps(tools_called, ensure_ascii=False), duration_ms, time.time())
        )
        conn.commit()

    def get_traces(self, project_id: str, agent: str = None, iteration: int = None) -> list[dict]:
        """Get traces, optionally filtered."""
        conn = self._get_conn()
        query = "SELECT * FROM agent_traces WHERE project_id = ?"
        params: list[Any] = [project_id]
        if agent:
            query += " AND agent = ?"
            params.append(agent)
        if iteration is not None:
            query += " AND iteration = ?"
            params.append(iteration)
        query += " ORDER BY created_at ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
