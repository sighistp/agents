"""Tests for P1.7: LLM message sliding window."""
from blueprint.utils.llm import trim_messages


def test_short_messages_unchanged():
    """Messages under limit should pass through unchanged."""
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    result = trim_messages(messages, max_messages=20)
    assert len(result) == 10


def test_long_messages_trimmed():
    """Messages over limit should be trimmed."""
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
    result = trim_messages(messages, max_messages=20)
    assert len(result) == 20
    # Should contain a summary message
    assert any("omitted" in m.get("content", "") for m in result)


def test_system_messages_preserved():
    """System messages should always be preserved."""
    messages = [
        {"role": "system", "content": "You are a developer."},
    ] + [{"role": "user", "content": f"msg {i}"} for i in range(50)]
    result = trim_messages(messages, max_messages=20)
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "You are a developer."


def test_recent_messages_kept():
    """Most recent messages should be kept."""
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
    result = trim_messages(messages, max_messages=20)
    # Last message should be msg 49
    assert "msg 49" in result[-1]["content"]


def test_empty_messages():
    """Empty message list should return empty."""
    result = trim_messages([], max_messages=20)
    assert result == []


def test_exact_limit_unchanged():
    """Messages exactly at limit should pass through unchanged."""
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
    result = trim_messages(messages, max_messages=20)
    assert len(result) == 20
    assert not any("omitted" in m.get("content", "") for m in result)
