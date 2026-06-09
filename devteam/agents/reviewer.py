"""Reviewer Agent module.

Responsible for code review and quality assurance.
Uses tool-calling loop: file_read to examine code, done to submit verdict.
"""
import json
from typing import Any

from devteam.agents.tools import REVIEWER_TOOLS, serialize_call, get_call_name, get_call_args
from devteam.agents.tool_executor import execute_tool
from devteam.utils.llm import call_llm_with_tools
from devteam.utils.logger import get_logger

logger = get_logger("reviewer")

MAX_STEPS = 5

# ── Prompts ──────────────────────────────────────────────────────────────────

REVIEWER_SYSTEM_PROMPT = """你是代码审查专家。你的任务是对项目代码进行全面审查。

## 工具
- file_read: 读取文件内容（逐文件审查）
- done: 完成审查，输出最终结论

## 审查规则
1. 用 file_read 逐文件读取和审查代码
2. 检查以下维度：
   - 安全漏洞（SQL注入、XSS、路径遍历等）
   - 逻辑错误（空值处理、边界条件、类型错误等）
   - 代码风格（命名规范、注释、代码重复等）
   - 边界条件（异常处理、输入验证等）
   - Placeholder/TODO（未完成的部分）
3. 每个问题必须指出具体文件和行号
4. 审查完成后调用 done 工具提交结论

## done 工具参数
- summary: 审查总结（必填）
- review_approved: true/false（是否通过）
- review_comments: 问题列表，每个问题包含 file, line, severity, description, suggestion"""


# ── Agent Node ──────────────────────────────────────────────────────────────

def reviewer_agent(state: dict) -> dict[str, Any]:
    """Reviewer agent: tool-loop based code review.

    Args:
        state: Current ProjectState dict

    Returns:
        State update dict with review_approved, review_comments, messages
    """
    messages = list(state.get("messages", []))
    files = state.get("files", {})
    requirement = state.get("requirement", "")
    project_dir = state.get("project_dir", ".")

    # Build initial prompt
    system_msg = {"role": "system", "content": REVIEWER_SYSTEM_PROMPT}
    user_content = f"请审查以下项目的代码。\n\n用户需求：{requirement}\n\n项目文件列表：\n"
    for path in files:
        user_content += f"- {path}\n"
    user_msg = {"role": "user", "content": user_content}

    llm_messages = [system_msg, user_msg]

    collected_review_approved = True
    collected_review_comments = []
    done_result = None
    error = None

    for step in range(MAX_STEPS):
        response = call_llm_with_tools(llm_messages, REVIEWER_TOOLS)

        # No tool calls → implicit done
        if not response.tool_calls:
            messages.append({
                "role": "assistant", "name": "reviewer",
                "content": response.content or "审查完成",
            })
            break

        # One assistant message with all tool_calls
        llm_messages.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [serialize_call(tc) for tc in response.tool_calls]
        })

        # Execute each tool
        for tc in response.tool_calls:
            tool_name = get_call_name(tc)
            args = get_call_args(tc)
            tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id
            result = execute_tool(tc, project_dir)
            llm_messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

            if tool_name == "done":
                done_result = args

        # All tool_calls processed, check if done
        if done_result:
            collected_review_approved = done_result.get("review_approved", True)
            collected_review_comments = done_result.get("review_comments", [])
            summary = done_result.get("summary", "审查完成")
            messages.append({
                "role": "assistant", "name": "reviewer",
                "content": f"审查{'通过' if collected_review_approved else '不通过'}：{summary}",
            })
            break
    else:
        # Loop completed without done — exceeded max steps
        error = f"超过最大步数({MAX_STEPS})"

    return {
        "error": error,
        "review_approved": collected_review_approved,
        "review_comments": collected_review_comments,
        "messages": messages,
    }
