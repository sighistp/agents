"""Tests for Proposer-Critic discussion module."""
import pytest


def test_proposer_critic_discuss_exists():
    """proposer_critic_discuss function should be importable."""
    from devteam.agents.discussion import proposer_critic_discuss
    assert callable(proposer_critic_discuss)


def test_discussion_config_exists():
    """DISCUSSION_CONFIG should be defined."""
    from devteam.agents.discussion import DISCUSSION_CONFIG
    assert isinstance(DISCUSSION_CONFIG, dict)
    assert "pm" in DISCUSSION_CONFIG
    assert "architect" in DISCUSSION_CONFIG
    assert "developer" in DISCUSSION_CONFIG


def test_discussion_config_pm_settings():
    """PM config should have correct settings."""
    from devteam.agents.discussion import DISCUSSION_CONFIG
    pm_config = DISCUSSION_CONFIG["pm"]
    # Default is mini mode (discussion disabled)
    assert pm_config["enabled"] is False
    assert pm_config["max_rounds"] == 1
    assert pm_config["mode"] == "full"


def test_discussion_config_developer_settings():
    """Developer config should have correct settings."""
    from devteam.agents.discussion import DISCUSSION_CONFIG
    dev_config = DISCUSSION_CONFIG["developer"]
    # Default is mini mode (discussion disabled)
    assert dev_config["enabled"] is False
    assert dev_config["max_rounds"] == 1
    assert dev_config["mode"] == "post_review"


def test_discussion_config_tester_disabled():
    """Tester should have discussion disabled."""
    from devteam.agents.discussion import DISCUSSION_CONFIG
    assert DISCUSSION_CONFIG["tester"]["enabled"] == False


def test_discussion_config_reviewer_disabled():
    """Reviewer should have discussion disabled."""
    from devteam.agents.discussion import DISCUSSION_CONFIG
    assert DISCUSSION_CONFIG["reviewer"]["enabled"] == False


def test_proposer_critic_discuss_full_mode():
    """Full mode should run Proposer-Critic loop."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch, MagicMock

    # Mock LLM responses
    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "Looks good"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:  # Odd calls = proposer
            return proposer_response
        else:  # Even calls = critic
            return critic_response

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert isinstance(result, str)
    assert isinstance(discussion, list)


def test_proposer_critic_discuss_post_review_mode():
    """Post-review mode should generate then review once."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"files": [{"path": "main.py", "content": "print(1)"}]}'
    critic_response = '{"approved": true, "critical_issues": [], "suggestions": []}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return proposer_response
        else:
            return critic_response

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Generate code",
            proposer_prompt="You are a developer",
            critic_prompt="You are a critic",
            max_rounds=1,
            mode="post_review"
        )

    assert isinstance(result, str)
    assert isinstance(discussion, list)
    # post_review should call LLM exactly 2 times (generate + review)
    assert call_count == 2


def test_proposer_critic_discuss_stops_on_approval():
    """Discussion should stop when critic approves."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            return proposer_response
        else:
            return critic_response

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    # Should stop after 1 round (2 calls) since critic approved
    assert call_count == 2


def test_proposer_critic_discuss_continues_on_rejection():
    """Discussion should continue when critic rejects."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_reject = '{"approved": false, "issues": ["Missing feature"], "suggestion": "Add more"}'
    critic_approve = '{"approved": true, "issues": [], "suggestion": "Good now"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # First round: proposer + reject
            return proposer_response if call_count % 2 == 1 else critic_reject
        else:
            # Second round: proposer + approve
            return proposer_response if call_count % 2 == 1 else critic_approve

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    # Should run 2 rounds (4 calls) before approval
    assert call_count == 4


def test_proposer_critic_discuss_max_rounds():
    """Discussion should stop at max_rounds even if not approved."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_reject = '{"approved": false, "issues": ["Issue"], "suggestion": "Fix"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_reject

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=2,
            mode="full"
        )

    # Should stop after 2 rounds (4 calls) even though not approved
    assert call_count == 4


def test_proposer_critic_discuss_records_proposals():
    """Discussion should record each proposal."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    # Should have at least 1 round recorded
    assert len(discussion) >= 1
    assert "proposal" in discussion[0]
    assert "critique" in discussion[0]


def test_proposer_critic_discuss_records_critiques():
    """Discussion should record each critique."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert len(discussion) >= 1
    assert "approved" in discussion[0]["critique"]
    assert "issues" in discussion[0]["critique"]


def test_proposer_critic_discuss_handles_llm_error():
    """Discussion should re-raise LLM errors for proper handling upstream."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    with pytest.raises(Exception, match="API Error"):
        with patch("devteam.agents.discussion.call_llm", side_effect=Exception("API Error")):
            proposer_critic_discuss(
                task="Design a todo app",
                proposer_prompt="You are a PM",
                critic_prompt="You are a critic",
                max_rounds=3,
                mode="full"
            )


def test_proposer_critic_discuss_post_review_fixes_critical():
    """Post-review should fix critical issues."""
    from devteam.agents.discussion import proposer_critic_discuss
    from unittest.mock import patch

    code_response = '{"files": [{"path": "main.py", "content": "query = f\\"SELECT * FROM users WHERE id={user_id}\\""}]}'
    critic_reject = '{"approved": false, "critical_issues": ["SQL injection"], "suggestions": ["Use parameterized queries"]}'
    fixed_code = '{"files": [{"path": "main.py", "content": "query = \\"SELECT * FROM users WHERE id=?\\""}]}'

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return code_response
        elif call_count == 2:
            return critic_reject
        else:
            return fixed_code

    with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
        result, discussion = proposer_critic_discuss(
            task="Generate code",
            proposer_prompt="You are a developer",
            critic_prompt="You are a critic",
            max_rounds=1,
            mode="post_review"
        )

    # Should have called LLM 3 times (generate + review + fix)
    assert call_count == 3
