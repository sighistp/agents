"""Tests for project memory layer (SQLite)."""
import json
import pytest
import tempfile
import os

from devteam.utils.memory import ProjectMemory


@pytest.fixture
def memory():
    """Create a temporary database for testing."""
    db_path = os.path.join(tempfile.mkdtemp(), "test_memory.db")
    mem = ProjectMemory(db_path)
    yield mem
    mem.close()


# ── Snapshot Tests ──────────────────────────────────────────────────────────

def test_save_and_get_snapshot(memory):
    memory.save_snapshot("p1", requirement="build a calculator", current_step="pm")
    snap = memory.get_snapshot("p1")
    assert snap is not None
    assert snap["requirement"] == "build a calculator"
    assert snap["current_step"] == "pm"
    assert snap["status"] == "active"


def test_update_snapshot(memory):
    memory.save_snapshot("p1", requirement="test", current_step="pm")
    memory.save_snapshot("p1", current_step="developer", iteration=2)
    snap = memory.get_snapshot("p1")
    assert snap["current_step"] == "developer"
    assert snap["iteration"] == 2


def test_get_nonexistent_snapshot(memory):
    assert memory.get_snapshot("nonexistent") is None


def test_save_snapshot_rejects_invalid_columns(memory):
    """C1: save_snapshot should reject invalid column names."""
    with pytest.raises(ValueError, match="Invalid snapshot columns"):
        memory.save_snapshot("p1", requirement="test", evil_column="drop table")


# ── Message Tests ───────────────────────────────────────────────────────────

def test_save_and_get_messages(memory):
    memory.save_message("p1", "user", "user", "做一个计算器")
    memory.save_message("p1", "assistant", "pm", "已拆分为3个用户故事")
    msgs = memory.get_messages("p1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["name"] == "pm"


def test_messages_isolated_by_project(memory):
    memory.save_message("p1", "user", "user", "项目1")
    memory.save_message("p2", "user", "user", "项目2")
    assert len(memory.get_messages("p1")) == 1
    assert len(memory.get_messages("p2")) == 1
    assert memory.get_messages("p1")[0]["content"] == "项目1"


def test_messages_empty_project(memory):
    assert memory.get_messages("nonexistent") == []


# ── Execution Tests ─────────────────────────────────────────────────────────

def test_save_execution(memory):
    memory.save_execution("p1", "developer", 1,
                          input_summary="需求：计算器",
                          tool_calls=[{"name": "file_write", "path": "main.py"}],
                          result_summary="生成了2个文件",
                          status="success")


def test_developer_context(memory):
    memory.save_execution("p1", "developer", 1, result_summary="第1轮开发")
    memory.save_execution("p1", "tester", 1, result_summary="第1轮测试失败")
    context = memory.get_developer_context("p1", 2)
    assert "developer" in context
    assert "tester" in context
    assert "第1轮" in context


def test_developer_context_empty(memory):
    assert memory.get_developer_context("p1", 1) == ""


def test_developer_context_limited(memory):
    """Should return recent iterations (last 2 iterations)."""
    memory.save_execution("p1", "tester", 1, result_summary="第1轮")
    memory.save_execution("p1", "developer", 1, result_summary="第1轮开发")
    memory.save_execution("p1", "tester", 2, result_summary="第2轮")
    memory.save_execution("p1", "developer", 2, result_summary="第2轮开发")
    memory.save_execution("p1", "tester", 3, result_summary="第3轮")

    context = memory.get_developer_context("p1", 3)
    # iteration >= (3-2) = 1, so all 3 iterations returned
    # But limited to 6 rows
    assert "第1轮" in context
    assert "第2轮" in context
    assert "第3轮" in context


def test_execution_status_icon(memory):
    memory.save_execution("p1", "tester", 1, result_summary="通过", status="success")
    memory.save_execution("p1", "developer", 1, result_summary="失败", status="error")
    context = memory.get_developer_context("p1", 2)
    assert "✅" in context
    assert "❌" in context


# ── Cleanup Tests ───────────────────────────────────────────────────────────

def test_cleanup(memory):
    memory.save_snapshot("old", requirement="old", status="completed")
    memory.save_message("old", "user", "user", "msg")
    memory.save_execution("old", "developer", 1, result_summary="done")
    # days=1 won't delete recent projects, but the function should not error
    memory.cleanup_old_projects(days=1)
    # Recent projects survive cleanup
    assert memory.get_snapshot("old") is not None


def test_cleanup_with_old_data(memory):
    """Cleanup should delete projects older than N days."""
    memory.save_snapshot("old_project", requirement="old", status="completed")
    memory.save_message("old_project", "user", "user", "msg")
    memory.save_execution("old_project", "developer", 1, result_summary="done")

    # Backdate the project
    conn = memory._get_conn()
    conn.execute(
        "UPDATE project_snapshots SET created_at = '2020-01-01 00:00:00' WHERE project_id = ?",
        ("old_project",)
    )
    conn.commit()

    # Create a recent project
    memory.save_snapshot("new_project", requirement="new", status="active")

    # Cleanup with days=1 should delete the old project
    memory.cleanup_old_projects(days=1)

    assert memory.get_snapshot("old_project") is None
    assert memory.get_messages("old_project") == []
    assert memory.get_snapshot("new_project") is not None


# ── Message Limit Tests ───────────────────────────────────────────────────

def test_message_limit_returns_most_recent(memory):
    """get_messages should return at most _MAX_RESTORE_MESSAGES (200) messages."""
    # Write 210 messages
    for i in range(210):
        memory.save_message("p1", "user", "user", f"message {i}")

    msgs = memory.get_messages("p1")
    assert len(msgs) == 200
    # Should be the most recent 200 (messages 10-209)
    assert msgs[0]["content"] == "message 10"
    assert msgs[-1]["content"] == "message 209"


def test_message_limit_custom_limit(memory):
    """get_messages should respect custom limit parameter."""
    for i in range(10):
        memory.save_message("p1", "user", "user", f"message {i}")

    msgs = memory.get_messages("p1", limit=5)
    assert len(msgs) == 5
    assert msgs[0]["content"] == "message 5"
    assert msgs[-1]["content"] == "message 9"


# ── Concurrency Tests ─────────────────────────────────────────────────────

def test_concurrent_access(memory):
    """Multiple threads should each get their own connection (threading.local)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    errors = []

    def write_and_read(thread_id):
        try:
            for i in range(5):
                memory.save_message(f"proj-{thread_id}", "user", "user", f"msg-{i}")
            msgs = memory.get_messages(f"proj-{thread_id}")
            assert len(msgs) == 5, f"Thread {thread_id}: expected 5 messages, got {len(msgs)}"
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_and_read, i) for i in range(5)]
        for f in as_completed(futures):
            f.result()

    assert errors == [], f"Concurrent access errors: {errors}"

    # Each project should have its own 5 messages
    for i in range(5):
        assert len(memory.get_messages(f"proj-{i}")) == 5


# ── Conversation Tests ─────────────────────────────────────────────────────

def test_save_and_get_conversation(memory):
    """save_conversation stores conversation, get_conversations retrieves it."""
    memory.save_conversation("proj-1", "developer", 1, [
        {"role": "assistant", "content": "写入 main.py"},
        {"role": "tool", "content": '{"success": true}'}
    ])
    convs = memory.get_conversations("proj-1")
    assert len(convs) == 1
    assert convs[0]["agent_name"] == "developer"
    assert convs[0]["iteration"] == 1
    msgs = json.loads(convs[0]["messages"])
    assert len(msgs) == 2
    assert msgs[0]["role"] == "assistant"


def test_get_conversations_empty(memory):
    """No conversations returns empty list."""
    convs = memory.get_conversations("nonexistent")
    assert convs == []


def test_save_execution_with_tool_calls(memory):
    """save_execution can store tool_calls field, get_executions retrieves it."""
    memory.save_execution("proj-1", "developer", 1, "写入 3 个文件",
                          result_summary="success",
                          tool_calls=[{"name": "file_write", "args_summary": "main.py"}])
    execs = memory.get_executions("proj-1")
    assert len(execs) == 1
    assert execs[0]["tool_calls"] is not None
