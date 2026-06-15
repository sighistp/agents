"""Reviewer Agent module.

Responsible for code review and quality assurance.
Uses tool-calling loop: file_read to examine code, done to submit verdict.
"""
import json
from typing import Any

from devteam.agents.tools import REVIEWER_TOOLS, serialize_call, get_call_name, get_call_args
from devteam.agents.tool_executor import execute_tool
import asyncio
from devteam.utils.llm import call_llm_with_tools_async
from devteam.utils.logger import get_logger

logger = get_logger("reviewer")

MAX_STEPS = 5

# ── Prompts ──────────────────────────────────────────────────────────────────

REVIEWER_SYSTEM_PROMPT = """你是代码审查专家。你的任务是对项目代码进行全面审查。

## 审查流程
1. 先用 file_read 通读全部代码，理解项目结构
2. 逐文件审查，重点检查：
   - 安全漏洞（注入、XSS、路径遍历）
   - 逻辑错误（空值、边界、类型错误、异常未处理）
   - 完整性（TODO、placeholder、未实现的功能）
3. 每个问题必须指出具体文件和行号
4. 汇总问题，判定通过/不通过
4. 调用 done 工具提交结论

## 通过标准（与系统路由对齐）
- review_approved=true → 代码进入交付阶段
- review_approved=false → 代码回到 Developer 重做
- 无 critical 问题 → 通过
- 有 critical 问题 → 不通过

## 常见错误（避免）
❌ 只说"代码有问题"不给具体位置和建议
❌ suggestion 只写"建议修复"不说明怎么修

## done 工具参数
- summary: 审查总结（必填）
- review_approved: true/false（是否通过）
- review_comments: 问题列表，每个问题包含 file, line, severity, description, suggestion
  - suggestion 必须是具体的修复方案，不能只说"建议修复"

## 错误恢复
如果你收到"上一次执行失败"的提示，先理解错误原因，不要重复同样的操作。"""


# ── Agent Node ──────────────────────────────────────────────────────────────

async def reviewer_agent(state: dict) -> dict[str, Any]:
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
    logger.info(f"Reviewer started, files: {list(files.keys())}")

    # Build initial prompt
    system_msg = {"role": "system", "content": REVIEWER_SYSTEM_PROMPT}
    user_content = f"请审查以下项目的代码。\n\n用户需求：{requirement}\n\n项目文件列表：\n"
    for path in files:
        user_content += f"- {path}\n"

    # 注入上一次的错误信息
    prev_error = state.get("error")
    if prev_error:
        user_content += f"\n⚠️ 上一次执行失败，错误：{prev_error[:500]}\n请避免重复同样的错误。\n"

    user_msg = {"role": "user", "content": user_content}

    llm_messages = [system_msg, user_msg]

    collected_review_approved = True
    collected_review_comments = []
    done_result = None
    error = None

    for step in range(MAX_STEPS):
        response = await call_llm_with_tools_async(llm_messages, REVIEWER_TOOLS)

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
            result = await asyncio.to_thread(execute_tool, tc, project_dir)
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
            logger.info(f"Reviewer done: approved={collected_review_approved}, summary={summary[:80]}")
            messages.append({
                "role": "assistant", "name": "reviewer",
                "content": f"审查{'通过' if collected_review_approved else '不通过'}：{summary}",
            })
            break
    else:
        # Loop completed without done — exceeded max steps
        error = f"超过最大步数({MAX_STEPS})"
        collected_review_approved = False  # 超步数视为不通过

    return {
        "error": error,
        "review_approved": collected_review_approved,
        "review_comments": collected_review_comments,
        "_reviewer_retry_count": state.get("_reviewer_retry_count", 0) + 1 if error else 0,
        "messages": messages,
    }
