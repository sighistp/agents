"""Tests for Proposer-Critic discussion module."""
import pytest
from unittest.mock import patch, AsyncMock


def test_proposer_critic_discuss_exists():
    from blueprint.agents.discussion import proposer_critic_discuss
    assert callable(proposer_critic_discuss)


def test_discussion_config_exists():
    from blueprint.agents.discussion import DISCUSSION_CONFIG
    assert isinstance(DISCUSSION_CONFIG, dict)
    assert "pm" in DISCUSSION_CONFIG
    assert "architect" in DISCUSSION_CONFIG
    assert "developer" in DISCUSSION_CONFIG


def test_discussion_config_pm_settings():
    from blueprint.agents.discussion import DISCUSSION_CONFIG
    pm_config = DISCUSSION_CONFIG["pm"]
    assert pm_config["enabled"] is False
    assert pm_config["max_rounds"] == 1
    assert pm_config["mode"] == "full"


def test_discussion_config_developer_settings():
    from blueprint.agents.discussion import DISCUSSION_CONFIG
    dev_config = DISCUSSION_CONFIG["developer"]
    assert dev_config["enabled"] is False
    assert dev_config["max_rounds"] == 1
    assert dev_config["mode"] == "post_review"


def test_discussion_config_tester_disabled():
    from blueprint.agents.discussion import DISCUSSION_CONFIG
    assert DISCUSSION_CONFIG["tester"]["enabled"] == False


def test_discussion_config_reviewer_disabled():
    from blueprint.agents.discussion import DISCUSSION_CONFIG
    assert DISCUSSION_CONFIG["reviewer"]["enabled"] == False


@pytest.mark.asyncio
async def test_proposer_critic_discuss_full_mode():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "Looks good"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert isinstance(result, str)
    assert isinstance(discussion, list)


@pytest.mark.asyncio
async def test_proposer_critic_discuss_post_review_mode():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"files": [{"path": "main.py", "content": "print(1)"}]}'
    critic_response = '{"approved": true, "critical_issues": [], "suggestions": []}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count == 1 else critic_response

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Generate code",
            proposer_prompt="You are a developer",
            critic_prompt="You are a critic",
            max_rounds=1,
            mode="post_review"
        )

    assert isinstance(result, str)
    assert isinstance(discussion, list)
    assert call_count == 2


@pytest.mark.asyncio
async def test_proposer_critic_discuss_stops_on_approval():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert call_count == 2


@pytest.mark.asyncio
async def test_proposer_critic_discuss_continues_on_rejection():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_reject = '{"approved": false, "issues": ["Missing feature"], "suggestion": "Add more"}'
    critic_approve = '{"approved": true, "issues": [], "suggestion": "Good now"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return proposer_response if call_count % 2 == 1 else critic_reject
        else:
            return proposer_response if call_count % 2 == 1 else critic_approve

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert call_count == 4


@pytest.mark.asyncio
async def test_proposer_critic_discuss_max_rounds():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_reject = '{"approved": false, "issues": ["Issue"], "suggestion": "Fix"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_reject

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=2,
            mode="full"
        )

    assert call_count == 4


@pytest.mark.asyncio
async def test_proposer_critic_discuss_records_proposals():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert len(discussion) >= 1
    assert "proposal" in discussion[0]
    assert "critique" in discussion[0]


@pytest.mark.asyncio
async def test_proposer_critic_discuss_records_critiques():
    from blueprint.agents.discussion import proposer_critic_discuss

    proposer_response = '{"user_stories": [{"id": "US-001", "title": "Test"}]}'
    critic_response = '{"approved": true, "issues": [], "suggestion": "LGTM"}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        return proposer_response if call_count % 2 == 1 else critic_response

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Design a todo app",
            proposer_prompt="You are a PM",
            critic_prompt="You are a critic",
            max_rounds=3,
            mode="full"
        )

    assert len(discussion) >= 1
    assert "approved" in discussion[0]["critique"]
    assert "issues" in discussion[0]["critique"]


@pytest.mark.asyncio
async def test_proposer_critic_discuss_handles_llm_error():
    from blueprint.agents.discussion import proposer_critic_discuss

    async def mock_call_llm_error(messages):
        raise Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm_error):
            await proposer_critic_discuss(
                task="Design a todo app",
                proposer_prompt="You are a PM",
                critic_prompt="You are a critic",
                max_rounds=3,
                mode="full"
            )


@pytest.mark.asyncio
async def test_proposer_critic_discuss_post_review_fixes_critical():
    from blueprint.agents.discussion import proposer_critic_discuss

    code_response = '{"files": [{"path": "main.py", "content": "query = f\\"SELECT * FROM users WHERE id={user_id}\\""}]}'
    critic_reject = '{"approved": false, "critical_issues": ["SQL injection"], "suggestions": ["Use parameterized queries"]}'
    fixed_code = '{"files": [{"path": "main.py", "content": "query = \\"SELECT * FROM users WHERE id=?\\""}]}'

    call_count = 0
    async def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return code_response
        elif call_count == 2:
            return critic_reject
        else:
            return fixed_code

    with patch("blueprint.agents.discussion.call_llm_async", side_effect=mock_call_llm):
        result, discussion = await proposer_critic_discuss(
            task="Generate code",
            proposer_prompt="You are a developer",
            critic_prompt="You are a critic",
            max_rounds=1,
            mode="post_review"
        )

    assert call_count == 3
