"""LangGraph graph structure for multi-agent workflow."""
from typing import Any

from langgraph.graph import END, START, StateGraph

from devteam.agents.state import ProjectState

# Import real agent nodes
from devteam.agents.pm import pm_agent
from devteam.agents.architect import architect_agent
from devteam.agents.developer import developer_agent
from devteam.agents.tester import tester_agent
from devteam.agents.reviewer import reviewer_agent


# ── Special Nodes ────────────────────────────────────────────────────────────

def human_confirm_node(state: ProjectState) -> dict[str, Any]:
    """Human confirm node: wait for user confirmation using interrupt.

    Uses LangGraph's interrupt() to pause execution and wait for user input.
    """
    import logging
    logger = logging.getLogger(__name__)
    from langgraph.types import interrupt

    # Check if human has already approved/rejected (from resume)
    human_approved = state.get("human_approved")
    if human_approved is not None:
        logger.info(f"Human confirm: already approved={human_approved}")
        return {"human_approved": human_approved}

    # Prepare architecture data for display
    architecture = state.get("architecture", {})
    api_definitions = state.get("api_definitions", [])
    data_models = state.get("data_models", [])

    logger.info("Human confirm: calling interrupt() to pause for user confirmation")

    # Interrupt and wait for user confirmation
    response = interrupt({
        "type": "confirm",
        "message": "请确认以下架构设计",
        "architecture": architecture,
        "api_definitions": api_definitions,
        "data_models": data_models
    })

    logger.info(f"Human confirm: user responded with {response}")

    # Process user response (can be dict, string, or bool)
    if isinstance(response, dict):
        approved = response.get("approved", False)
    elif isinstance(response, str):
        approved = response.lower() in ("approved", "true", "yes")
    else:
        approved = bool(response)

    return {
        "human_approved": approved,
        "current_agent": "developer" if approved else "architect"
    }


def deliver_node(state: ProjectState) -> dict[str, Any]:
    """Deliver node: package and save output."""
    import json
    from devteam.config import settings
    import re
    from pathlib import Path

    project_id = state.get("project_id", "default")
    files = state.get("files", {})

    # Check if there are files to deliver
    if not files:
        return {
            "status": "failed",
            "error": "没有生成任何文件",
            "files": {},
            "messages": [{"role": "assistant", "name": "system",
                          "content": "交付失败：没有生成任何文件。可能是Agent执行失败或需求无法实现。"}],
        }

    # Validate project_id to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_id):
        return {
            "status": "failed",
            "error": f"Invalid project_id: {project_id}",
            "files": {},
            "messages": [{"role": "assistant", "name": "system",
                          "content": f"项目ID无效：{project_id}"}],
        }

    # Use configured project_dir from settings
    base_dir = Path(settings.project_dir) if settings.project_dir else Path("projects")
    project_dir = base_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write code files (with path validation)
    for file_path, content in files.items():
        # Validate file path to prevent traversal
        if ".." in file_path or file_path.startswith(("/", "\\")):
            continue  # Skip unsafe paths
        full_path = (project_dir / file_path).resolve()
        if not full_path.is_relative_to(project_dir.resolve()):
            continue  # Path escapes project dir
        if full_path.exists() and full_path.read_text(encoding="utf-8") == content:
            continue
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # Write metadata
    meta = {
        "requirement": state.get("requirement", ""),
        "user_stories": state.get("user_stories", []),
        "features": state.get("features", []),
        "architecture": state.get("architecture", {}),
        "iteration": state.get("iteration", 0),
    }
    (project_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return {
        "status": "delivered",
        "current_agent": "done",
        "files": files,  # 返回文件内容供前端下载
        "project_path": str(project_dir),
        "messages": [{"role": "assistant", "name": "system",
                      "content": f"项目完成！文件已保存到 {project_dir}"}],
    }


# ── Route Functions ─────────────────────────────────────────────────────────

def route_by_complexity(state: ProjectState) -> str:
    """Route by requirement complexity. Simple requirements skip PM."""
    req = state.get("requirement", "")
    # 简单需求：很短、没有架构相关关键词
    complex_keywords = [
        "系统", "平台", "架构", "数据库", "用户注册", "登录", "API", "后台",
        "web", "Web", "WEB", "应用", "网站", "前端", "后端", "全栈",
        "管理", "用户", "认证", "权限", "部署",
    ]
    # 极短需求（<15字）且无复杂关键词 → 直接写代码
    if len(req) < 15 and not any(kw in req for kw in complex_keywords):
        return "developer"
    return "pm"


def route_after_pm(state: ProjectState) -> str:
    """Route after PM node."""
    error = state.get("error")
    if error:
        if "timeout" in error.lower():
            return END
        retry_count = state.get("_pm_retry_count", 0)
        if retry_count >= 2:
            return END
        return "pm"
    return "proceed"


def route_after_architect(state: ProjectState) -> str:
    """Route after Architect node."""
    import logging
    logger = logging.getLogger(__name__)

    error = state.get("error")
    if error:
        logger.info(f"Architect error: {error}")
        if "timeout" in error.lower():
            return END
        retry_count = state.get("_architect_retry_count", 0)
        if retry_count >= 2:
            return END
        return "architect"

    need_confirm = state.get("need_human_confirm", True)
    logger.info(f"Architect done, need_human_confirm={need_confirm}")

    if need_confirm:
        return "confirm"
    return "auto"


def route_after_human(state: ProjectState) -> str:
    """Route after human confirmation."""
    if state.get("human_approved"):
        return "approve"
    return "reject"


def route_after_developer(state: ProjectState) -> str:
    """Route after Developer node.

    Routes:
    - tester: Success, move to Tester
    - developer: Non-security error, retry (max 2 times)
    - END: Security error or max retries reached
    """
    error = state.get("error")
    if error:
        if "security" in error.lower() or "path" in error.lower():
            return END
        # Check retry count to prevent infinite loops
        retry_count = state.get("_developer_retry_count", 0)
        if retry_count >= 2:
            return END  # Max retries reached
        return "developer"  # Retry
    return "tester"


def route_after_test(state: ProjectState) -> str:
    """Route after Tester node."""
    if state.get("test_passed", False):
        return "pass"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "pass"
    return "fail"


def route_after_review(state: ProjectState) -> str:
    """Route after Reviewer node.

    Routes:
    - approve: No critical issues, proceed to delivery
    - reject: Has issues, go back to Developer for fixes
    - redesign: Has architectural issues, go back to Architect
    - human_confirm: Max iterations reached, let human decide
    """
    if state.get("review_approved", False):
        return "approve"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "human_confirm"

    comments = state.get("review_comments", [])
    has_architectural_issues = any(
        c.get("severity") == "critical" and
        any(keyword in c.get("description", "").lower()
            for keyword in ["architecture", "design", "structure", "refactor",
                            "架构", "设计", "重构"])
        for c in comments
    )

    if has_architectural_issues and state["iteration"] < 2:
        return "redesign"  # Go back to Architect

    return "reject"  # Go back to Developer for fixes


# ── Graph Construction ──────────────────────────────────────────────────────

def create_graph():
    """Create and compile the LangGraph workflow.

    Flow: PM → Architect → Developer → Tester → Reviewer → Deliver

    Returns:
        Compiled LangGraph app
    """
    graph = StateGraph(ProjectState)

    # Add nodes (using real agent implementations)
    graph.add_node("pm", pm_agent)
    graph.add_node("architect", architect_agent)
    graph.add_node("human_confirm", human_confirm_node)
    graph.add_node("developer", developer_agent)
    graph.add_node("tester", tester_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("deliver", deliver_node)

    # Entry point — simple requirements skip PM
    graph.add_conditional_edges(START, route_by_complexity, {
        "pm": "pm",
        "developer": "developer",
    })

    # PM conditional edges
    graph.add_conditional_edges("pm", route_after_pm, {
        "proceed": "architect",
        "pm": "pm",  # Error retry
        END: END,
    })

    # Architect conditional edges
    graph.add_conditional_edges("architect", route_after_architect, {
        "auto": "developer",
        "confirm": "human_confirm",
        "architect": "architect",  # Error retry
        END: END,
    })

    # Human confirm conditional edges
    graph.add_conditional_edges("human_confirm", route_after_human, {
        "approve": "developer",
        "reject": "architect",
    })

    # Developer conditional edges
    graph.add_conditional_edges("developer", route_after_developer, {
        "tester": "tester",
        "developer": "developer",  # Error retry
        END: END,
    })

    # Tester conditional edges
    graph.add_conditional_edges("tester", route_after_test, {
        "pass": "reviewer",
        "fail": "developer",  # Tests fail → Developer fixes
    })

    # Reviewer conditional edges
    graph.add_conditional_edges("reviewer", route_after_review, {
        "approve": "deliver",
        "reject": "developer",
        "redesign": "architect",
        "human_confirm": "human_confirm",  # 冲突仲裁：循环上限时让人决定
    })

    # Deliver to END
    graph.add_edge("deliver", END)

    # Compile with checkpointer for interrupt/resume support
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
