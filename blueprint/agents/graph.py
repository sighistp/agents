"""LangGraph graph structure for multi-agent workflow."""
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from blueprint.agents.state import ProjectState

logger = logging.getLogger("blueprint.graph")

# Import real agent nodes
from blueprint.agents.pm import pm_agent
from blueprint.agents.architect import architect_agent
from blueprint.agents.developer import developer_agent
from blueprint.agents.tester import tester_agent
from blueprint.agents.reviewer import reviewer_agent


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

    # 判断是架构确认还是 Developer 重试失败后的用户决策
    error = state.get("error", "")
    is_dev_retry = error and "超过最大步数" in error

    if is_dev_retry:
        # Developer 重试失败，让用户决定
        logger.info("Human confirm: Developer max retries, asking user")
        response = interrupt({
            "type": "confirm",
            "message": f"Developer 已重试 2 次仍失败：{error[:200]}\n是否继续尝试？",
            "error": error,
            "files": list(state.get("files", {}).keys()),
        })
    else:
        # 正常架构确认流程
        architecture = state.get("architecture", {})
        api_definitions = state.get("api_definitions", [])
        data_models = state.get("data_models", [])
        logger.info("Human confirm: calling interrupt() to pause for user confirmation")
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

    if is_dev_retry:
        if approved:
            # 用户决定继续 → 重置 retry count，重新从 Developer 开始
            return {
                "human_approved": True,
                "current_agent": "developer",
                "_developer_retry_count": 0,
                "error": None,
            }
        else:
            # 用户决定停止 → 交付已有文件
            return {
                "human_approved": True,
                "current_agent": "deliver",
                "error": None,
            }

    return {
        "human_approved": approved,
        "current_agent": "developer" if approved else "architect"
    }


# ── Post-Deliver Hooks ──────────────────────────────────────────────────────
# Each hook is called after deliver_node writes files.
# Signature: hook(state: dict, project_dir: Path) -> None
# Failure in any hook must NOT prevent delivery.

_post_deliver_hooks: list = []


def _run_post_deliver_hooks(state: dict, project_dir):
    """Execute all post-deliver hooks. Failures are logged but don't break delivery."""
    for hook in _post_deliver_hooks:
        try:
            hook(state, project_dir)
        except Exception as e:
            logger.warning(f"Post-deliver hook {getattr(hook, '__name__', '?')} failed: {e}")


def save_snapshot_hook(state: dict, project_dir):
    """Save a diff snapshot for the delivered iteration."""
    from blueprint.utils.diff_engine import DiffEngine
    engine = DiffEngine(str(project_dir))
    engine.save_snapshot(state.get("iteration", 0))


def quality_score_hook(state: dict, project_dir):
    """Calculate and cache quality score."""
    import json as _json
    from blueprint.utils.quality_scorer import QualityScorer
    scorer = QualityScorer()
    result = scorer.score_project(str(project_dir))
    score_dir = project_dir.parent.parent / "data" / "scores"
    score_dir.mkdir(parents=True, exist_ok=True)
    (score_dir / f"{project_dir.name}.json").write_text(
        _json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


def security_scan_hook(state: dict, project_dir):
    """Run security scan and cache results."""
    import json as _json
    from blueprint.utils.security_scanner import SecurityScanner
    scanner = SecurityScanner()
    result = scanner.scan_project(str(project_dir))
    scan_dir = project_dir.parent.parent / "data" / "security"
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / f"{project_dir.name}.json").write_text(
        _json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


def generate_docs_hook(state: dict, project_dir):
    """Generate documentation files in _blueprint/ subdirectory."""
    from blueprint.utils.doc_generator import DocGenerator
    gen = DocGenerator()
    docs = gen.generate(str(project_dir), state.get("requirement", ""))
    doc_dir = project_dir / "_blueprint"
    doc_dir.mkdir(exist_ok=True)
    for name, content in docs.items():
        target = doc_dir / f"{name}.md"
        if not target.exists():
            target.write_text(content, encoding="utf-8")


def generate_deploy_hook(state: dict, project_dir):
    """Generate deployment files in _blueprint/ subdirectory."""
    from blueprint.utils.deploy_generator import DeployGenerator
    gen = DeployGenerator()
    files = gen.generate(str(project_dir))
    deploy_dir = project_dir / "_blueprint"
    deploy_dir.mkdir(exist_ok=True)
    for name, content in files.items():
        target = deploy_dir / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")


def webhook_hook(state: dict, project_dir):
    """Send webhook notification on project delivery (sync, best-effort)."""
    import json as _json
    from pathlib import Path as _Path
    from blueprint.config import settings

    config_path = _Path(settings.project_dir if settings.project_dir else "projects").parent / "data" / "webhooks.json"
    if not config_path.exists():
        return

    try:
        webhooks_data = _json.loads(config_path.read_text(encoding="utf-8"))
        webhooks = webhooks_data.get("webhooks", [])
        if not webhooks:
            return

        import hashlib
        import hmac
        import time
        import httpx

        payload = {
            "event": "project.completed",
            "timestamp": time.time(),
            "data": {
                "project_id": state.get("project_id", ""),
                "requirement": state.get("requirement", ""),
                "files_count": len(state.get("files", {})),
                "iteration": state.get("iteration", 0),
            },
        }
        body_bytes = _json.dumps(payload, ensure_ascii=False).encode("utf-8")

        with httpx.Client(timeout=10) as client:
            for wh in webhooks:
                events = wh.get("events", ["*"])
                if "*" not in events and "project.completed" not in events:
                    continue
                headers = {"Content-Type": "application/json"}
                secret = wh.get("secret")
                if secret:
                    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
                    headers["X-Webhook-Signature"] = f"sha256={sig}"
                try:
                    client.post(wh["url"], content=body_bytes, headers=headers)
                except Exception:
                    pass
    except Exception:
        pass


# Register default hooks
_post_deliver_hooks.extend([
    save_snapshot_hook,
    quality_score_hook,
    security_scan_hook,
    generate_docs_hook,
    generate_deploy_hook,
    webhook_hook,
])


# ── Deliver Node ─────────────────────────────────────────────────────────────

def deliver_node(state: ProjectState) -> dict[str, Any]:
    """Deliver node: package and save output."""
    import json
    from blueprint.config import settings
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

    # Run post-deliver hooks (snapshot, quality score, security scan)
    _run_post_deliver_hooks(state, project_dir)

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
    approved = state.get("human_approved")
    current_agent = state.get("current_agent", "")

    # Developer 重试失败后用户选择"停止"→ 直接交付
    if approved and current_agent == "deliver":
        return "deliver"

    if approved:
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
    files = list(state.get("files", {}).keys())
    retry_count = state.get("_developer_retry_count", 0)
    logger.info(f"route_after_developer: error={error!r}, files={files}, retry={retry_count}")
    if error:
        if "security" in error.lower() or "path" in error.lower():
            logger.info("route_after_developer → END (security)")
            return END
        # Check retry count to prevent infinite loops
        if retry_count >= 2:
            logger.info("route_after_developer → human_confirm (max retries, let user decide)")
            return "human_confirm"  # 让用户决定是否继续
        logger.info("route_after_developer → developer (retry)")
        return "developer"  # Retry
    logger.info("route_after_developer → tester")
    return "tester"


def route_after_test(state: ProjectState) -> str:
    """Route after Tester node."""
    test_passed = state.get("test_passed", False)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    tester_retry = state.get("_tester_retry_count", 0)
    error = state.get("error")
    logger.info(f"route_after_test: test_passed={test_passed}, iteration={iteration}/{max_iter}, tester_retry={tester_retry}, error={error!r}")
    if test_passed:
        logger.info("route_after_test → reviewer (pass)")
        return "pass"
    # Tester 自身崩溃重试超过 2 次，跳过 Tester 直接到 Reviewer
    if tester_retry >= 2:
        logger.info("route_after_test → reviewer (tester max retries)")
        return "pass"
    if iteration >= max_iter:
        logger.info("route_after_test → reviewer (max iterations)")
        return "pass"
    logger.info("route_after_test → developer (fail)")
    return "fail"


def route_after_review(state: ProjectState) -> str:
    """Route after Reviewer node.

    Routes:
    - approve: No critical issues, proceed to delivery
    - reject: Has issues, go back to Developer for fixes
    - redesign: Has architectural issues, go back to Architect
    - human_confirm: Max iterations reached, let human decide
    """
    approved = state.get("review_approved", False)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    reviewer_retry = state.get("_reviewer_retry_count", 0)
    error = state.get("error")
    logger.info(f"route_after_review: approved={approved}, iteration={iteration}/{max_iter}, reviewer_retry={reviewer_retry}, error={error!r}")
    if approved:
        logger.info("route_after_review → deliver (approved)")
        return "approve"
    if iteration >= max_iter:
        logger.info("route_after_review → deliver (max iterations)")
        # 达到最大迭代次数，直接交付（防止死循环）
        return "approve"
    # Reviewer 自身崩溃重试超过 2 次，直接交付
    if reviewer_retry >= 2:
        logger.info("route_after_review → deliver (reviewer max retries)")
        return "approve"

    comments = state.get("review_comments", [])
    has_architectural_issues = any(
        c.get("severity") == "critical" and
        any(keyword in c.get("description", "").lower()
            for keyword in ["architecture", "design", "structure", "refactor",
                            "架构", "设计", "重构"])
        for c in comments
    )

    if has_architectural_issues and state["iteration"] < 2:
        logger.info("route_after_review → architect (redesign)")
        return "redesign"  # Go back to Architect

    logger.info("route_after_review → developer (reject)")
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
        "deliver": "deliver",
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
    })

    # Deliver to END
    graph.add_edge("deliver", END)

    # Compile with checkpointer for interrupt/resume support
    # MemorySaver: state in memory, lost on restart
    # TODO: upgrade to SqliteSaver for persistence when needed
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
