"""Integration tests for the full DevTeam workflow.

Tests the end-to-end flow: requirement → PM → Architect → Developer → Tester → Reviewer → Deliver
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ── Test Helpers ─────────────────────────────────────────────────────────────

def _make_tool_call(name, arguments, call_id="call_1"):
    """Create a mock tool_call object (same pattern as unit tests)."""
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _make_response(content="", tool_calls=None):
    """Create a mock LLM response with .content and .tool_calls."""
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


# ── Integration Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_workflow_with_mock_llm():
    """Full workflow should complete with mocked LLM responses."""
    from devteam.agents.graph import create_graph
    from devteam.agents.state import create_initial_state

    # PM/Architect use call_llm_async (returns plain string)
    pm_response = '''
    {
        "user_stories": [{"id": "US-001", "title": "Create calculator", "description": "User can add numbers", "acceptance_criteria": ["Given two numbers, when added, then result is correct"], "priority": "high"}],
        "features": [{"name": "Addition", "description": "Basic addition", "priority": "high", "related_stories": ["US-001"]}],
        "technical_constraints": ["Must use Python"],
        "needs_clarification": false,
        "clarification_questions": []
    }
    '''

    architect_response = '''
    {
        "architecture_description": "Simple REST API",
        "tech_stack": {"backend": "FastAPI", "language": "Python"},
        "modules": ["api", "calculator"],
        "api_definitions": [{"method": "POST", "path": "/add", "description": "Add two numbers", "request_body": {"a": "int", "b": "int"}, "response_body": {"result": "int"}}],
        "data_models": []
    }
    '''

    # Developer/Tester/Reviewer use call_llm_with_tools (returns response with .tool_calls)
    # Developer: file_write then done (provide extras for potential retries)
    dev_responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "main.py", "content": "def add(a, b): return a + b"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成开发"})]),
    ] * 3  # Repeat to handle retries

    # Tester: execute_python then done (passed)
    tester_responses = [
        _make_response("", [_make_tool_call("execute_python", {"code": "assert add(1, 2) == 3"})]),
        _make_response("", [_make_tool_call("done", {"summary": "1 passed, 0 failed"})]),
    ] * 3

    # Reviewer: file_read then done (approved)
    reviewer_responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("", [_make_tool_call("done", {"summary": "代码质量良好", "review_approved": True})]),
    ] * 3

    # PM uses call_llm_async
    async def mock_pm_call_llm(messages):
        return pm_response

    # Architect uses call_llm_async
    async def mock_architect_call_llm(messages):
        return architect_response

    with patch("devteam.agents.pm.call_llm_async", side_effect=mock_pm_call_llm):
        with patch("devteam.agents.architect.call_llm_async", side_effect=mock_architect_call_llm):
            with patch("devteam.agents.developer.call_llm_with_tools", side_effect=dev_responses):
                with patch("devteam.agents.tester.call_llm_with_tools", side_effect=tester_responses):
                    with patch("devteam.agents.reviewer.call_llm_with_tools", side_effect=reviewer_responses):
                        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
                            def mock_execute_tool(call, project_dir=""):
                                name = call.function.name
                                if name == "file_write":
                                    return json.dumps({"success": True, "path": "test"})
                                elif name == "file_read":
                                    return json.dumps({"content": "print('hello')"})
                                elif name == "execute_python":
                                    return json.dumps({"returncode": 0, "stdout": "ok", "stderr": ""})
                                elif name == "done":
                                    return json.dumps({"status": "completed"})
                                return json.dumps({"success": True})
                            mock_exec.side_effect = mock_execute_tool
                            # Mock interrupt to auto-approve
                            with patch("langgraph.types.interrupt", return_value={"approved": True}):
                                app = create_graph()
                                # Use a complex requirement so route_by_complexity sends to PM
                                state = create_initial_state(
                                    "test-integration",
                                    "构建一个用户注册登录系统，包含API接口和数据库设计，需要支持后台管理功能"
                                )
                                state["need_human_confirm"] = False  # Skip human confirm for test

                                # Run the graph with config for checkpointer
                                config = {"configurable": {"thread_id": "test-integration"}}
                                result = await app.ainvoke(state, config=config)

    # Verify the workflow completed
    assert result.get("status") == "delivered"
    assert result.get("user_stories") is not None
    assert len(result.get("user_stories", [])) > 0
    assert result.get("architecture") is not None
    assert result.get("files") is not None
    assert len(result.get("files", {})) > 0


@pytest.mark.asyncio
async def test_workflow_stops_on_error():
    """Workflow should handle errors in agent nodes."""
    from devteam.agents.pm import pm_agent
    from devteam.agents.state import create_initial_state

    def mock_call_llm_error(messages):
        raise Exception("API Error")

    with patch("devteam.agents.pm.call_llm_async", side_effect=mock_call_llm_error):
        state = create_initial_state("test-error", "Build a calculator")
        result = await pm_agent(state)

    # Should have error information (may be wrapped in JSON parse error)
    assert result.get("error") is not None
    assert len(result.get("error", "")) > 0


@pytest.mark.asyncio
async def test_workflow_handles_pm_clarification():
    """Workflow should handle PM clarification request."""
    from devteam.agents.pm import pm_agent
    from devteam.agents.state import create_initial_state

    # Mock response with clarification needed
    clarification_response = '''
    {
        "user_stories": [{"id": "US-001", "title": "Create todo", "description": "User can create todo", "acceptance_criteria": ["Given a form, when submitted, then todo is created"], "priority": "high"}],
        "features": [],
        "technical_constraints": [],
        "needs_clarification": true,
        "clarification_questions": ["What database should be used?", "Is authentication required?"]
    }
    '''

    with patch("devteam.agents.pm.call_llm_async", return_value=clarification_response):
        state = create_initial_state("test-clarify", "Build something")
        result = await pm_agent(state)

    # Should detect clarification is needed
    assert result.get("needs_clarification") == True
    assert len(result.get("clarification_questions", [])) > 0


@pytest.mark.asyncio
async def test_workflow_handles_test_failure():
    """Workflow should handle test failures via tool-loop."""
    from devteam.agents.tester import tester_agent
    from devteam.agents.state import create_initial_state

    # Tester uses tool-loop: execute_python → done with failure summary
    responses = [
        _make_response("", [_make_tool_call("execute_python", {"code": "assert add(1, 2) == 4"})]),
        _make_response("", [_make_tool_call("done", {"summary": "1 passed, 1 failed. Failure: assert 3 == 4"})]),
    ]

    with patch("devteam.agents.tester.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"returncode": 1, "stdout": "", "stderr": "AssertionError"})
            state = create_initial_state("test-fail", "Build a calculator")
            state["files"] = {"main.py": "def add(a, b): return a + b"}
            result = tester_agent(state)

    # Should indicate test failure
    assert result.get("test_passed") == False


@pytest.mark.asyncio
async def test_workflow_handles_review_rejection():
    """Workflow should handle reviewer rejection via tool-loop."""
    from devteam.agents.reviewer import reviewer_agent
    from devteam.agents.state import create_initial_state

    # Reviewer uses tool-loop: file_read → done with rejection
    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("", [_make_tool_call("done", {
            "summary": "发现SQL注入漏洞",
            "review_approved": False,
            "review_comments": [{"file": "main.py", "line": 5, "severity": "critical", "description": "SQL injection", "suggestion": "Use parameterized queries"}]
        })]),
    ]

    with patch("devteam.agents.reviewer.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "query = f'SELECT * FROM users WHERE id={user_id}'"})
            state = create_initial_state("test-reject", "Build a user system")
            state["files"] = {"main.py": "query = f'SELECT * FROM users WHERE id={user_id}'"}
            state["test_passed"] = True
            state["test_results"] = []
            result = reviewer_agent(state)

    # Should indicate review rejection
    assert result.get("review_approved") == False


@pytest.mark.asyncio
async def test_workflow_iteration_tracking():
    """Workflow should track iteration count."""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    # Developer uses tool-loop: file_write → done
    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "main.py", "content": "print('hello')"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成"})]),
    ]

    with patch("devteam.agents.developer.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True})
            state = create_initial_state("test-iteration", "Build something")
            state["iteration"] = 1
            result = developer_agent(state)

    # Should increment iteration
    assert result.get("iteration") == 2


@pytest.mark.asyncio
async def test_workflow_file_generation():
    """Workflow should generate valid files."""
    from devteam.agents.developer import developer_agent
    from devteam.agents.state import create_initial_state

    # Developer uses tool-loop: file_write (x2) → done
    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "main.py", "content": "def hello(): return 'world'"})]),
        _make_response("", [_make_tool_call("file_write", {"path": "index.html", "content": "<html><body>Hello</body></html>"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成"})]),
    ]

    with patch("devteam.agents.developer.call_llm_with_tools", side_effect=responses):
        with patch("devteam.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True})
            state = create_initial_state("test-files", "Build a web app")
            result = developer_agent(state)

    # Should have generated files
    assert "files" in result
    assert len(result["files"]) == 2
    assert "main.py" in result["files"]
    assert "index.html" in result["files"]


@pytest.mark.asyncio
async def test_workflow_proposer_critic_integration():
    """Proposer-Critic should be integrated into PM agent."""
    from devteam.agents.pm import pm_agent
    from devteam.agents.state import create_initial_state

    # Mock responses for Proposer-Critic (uses sync call_llm)
    proposer_response = '''
    {
        "user_stories": [{"id": "US-001", "title": "Create todo", "description": "User can create todo", "acceptance_criteria": ["Given a form, when submitted, then todo is created"], "priority": "high"}],
        "features": [],
        "technical_constraints": [],
        "needs_clarification": false,
        "clarification_questions": []
    }
    '''

    critic_response = '''
    {
        "approved": true,
        "issues": [],
        "suggestion": "Looks good"
    }
    '''

    call_count = 0
    def mock_call_llm(messages):
        nonlocal call_count
        call_count += 1
        # Determine if this is a proposer or critic call based on content
        content = messages[-1].get("content", "") if messages else ""
        if "审查" in content or "review" in content.lower():
            return critic_response
        return proposer_response

    # Enable discussion for this test
    mock_config = {
        "pm": {"enabled": True, "max_rounds": 1, "mode": "full"},
        "architect": {"enabled": False, "max_rounds": 1, "mode": "full"},
        "developer": {"enabled": False, "max_rounds": 1, "mode": "post_review"},
        "tester": {"enabled": False},
        "reviewer": {"enabled": False},
    }

    with patch("devteam.agents.discussion.DISCUSSION_CONFIG", mock_config):
        with patch("devteam.agents.discussion.call_llm", side_effect=mock_call_llm):
            with patch("devteam.agents.discussion.get_discussion_config", return_value=mock_config):
                state = create_initial_state("test-pc", "Build a todo app")
                result = await pm_agent(state)

    # Should have completed successfully
    assert "user_stories" in result
    assert len(result["user_stories"]) > 0
    # Proposer-Critic should have been called multiple times (proposer + critic)
    assert call_count >= 2


def test_workflow_deliver_saves_files():
    """Deliver node should save files to disk."""
    from devteam.agents.graph import deliver_node

    state = {
        "project_id": "test-deliver",
        "requirement": "Build a calculator",
        "user_stories": [{"id": "US-001", "title": "Add numbers"}],
        "features": [],
        "architecture": {"description": "Simple API"},
        "files": {
            "main.py": "def add(a, b): return a + b",
            "test_main.py": "def test_add(): assert add(1, 2) == 3"
        },
        "iteration": 1,
    }

    result = deliver_node(state)

    # Should have saved files
    assert result.get("status") == "delivered"
    assert result.get("project_path") is not None
