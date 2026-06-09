"""Tester Agent module.

Responsible for running tests using a tool-calling loop.
Uses file_read and execute_python tools — no file_write.
"""
import json
from typing import Any

from devteam.agents.tools import TESTER_TOOLS, serialize_call, get_call_name, get_call_args
from devteam.agents.tool_executor import execute_tool
from devteam.utils.llm import call_llm_with_tools
from devteam.utils.logger import get_logger

logger = get_logger("tester")

# ── Prompts ──────────────────────────────────────────────────────────────────

TESTER_SYSTEM_PROMPT = """你是测试工程师，负责对项目代码进行测试。

规则：
- 用 file_read 读取需要测试的代码文件
- 用 execute_python 执行测试代码（可多次执行不同测试）
- 覆盖正常路径和边界条件
- 测试全部完成后调用 done 工具，summary 中说明通过/失败数量

你没有 file_write 权限，只能读取和执行。"""

MAX_STEPS = 8


# ── Helper Functions ─────────────────────────────────────────────────────────

def build_tester_messages(state: dict) -> list[dict]:
    """Build initial messages for tester agent tool loop."""
    messages = [{"role": "system", "content": TESTER_SYSTEM_PROMPT}]

    requirement = state.get("requirement", "")
    files = state.get("files", {})
    user_stories = state.get("user_stories", [])

    user_content = f"用户需求：{requirement}\n\n"
    user_content += "项目文件列表：\n"
    for path in files:
        user_content += f"- {path}\n"

    if user_stories:
        user_content += "\n用户故事（验收标准）：\n"
        for story in user_stories:
            user_content += f"- {story.get('id', '')}: {story.get('title', '')}\n"
            for criteria in story.get("acceptance_criteria", []):
                user_content += f"  * {criteria}\n"

    user_content += "\n请开始测试。先用 file_read 查看代码，再用 execute_python 执行测试。"
    messages.append({"role": "user", "content": user_content})

    return messages


def _extract_test_passed(summary: str, had_execution_errors: bool) -> bool:
    """Determine if tests passed from the done summary and actual execution results.

    Uses both LLM summary and actual tool execution results for reliability.
    """
    # If execute_python returned non-zero, tests failed regardless of summary
    if had_execution_errors:
        return False

    summary_lower = summary.lower()
    fail_indicators = ["fail", "error", "失败", "0 passed"]
    for indicator in fail_indicators:
        if indicator in summary_lower:
            if "0 fail" in summary_lower or "0 失败" in summary_lower or "0 error" in summary_lower:
                continue
            return False
    return True


# ── Agent Node ──────────────────────────────────────────────────────────────

def tester_agent(state: dict) -> dict[str, Any]:
    """Tester agent: tool-loop based testing.

    Iterates up to MAX_STEPS, calling LLM with tools and executing them.
    Returns state update with test_passed, test_results, messages.
    """
    messages = list(state.get("messages", []))
    collected_files = state.get("files", {})
    project_dir = state.get("project_dir", ".")

    try:
        # Build initial conversation
        llm_messages = build_tester_messages(state)

        test_passed = False
        test_results = []
        done_summary = ""
        had_execution_errors = False  # Track if any execute_python failed

        for step in range(MAX_STEPS):
            # Call LLM with tools
            response = call_llm_with_tools(llm_messages, TESTER_TOOLS)

            # Record assistant message
            assistant_msg = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = [serialize_call(tc) for tc in response.tool_calls]
            llm_messages.append(assistant_msg)

            # If no tool calls, treat as done
            if not response.tool_calls:
                messages.append({"role": "assistant", "name": "tester",
                                 "content": response.content or "测试完成"})
                break

            # Execute each tool call
            for tc in response.tool_calls:
                tool_name = get_call_name(tc)
                tool_args = get_call_args(tc)
                tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id

                # Execute the tool
                result_str = execute_tool(tc, project_dir)

                # Track execute_python failures
                if tool_name == "execute_python":
                    try:
                        exec_result = json.loads(result_str)
                        if exec_result.get("returncode", 0) != 0:
                            had_execution_errors = True
                    except (json.JSONDecodeError, AttributeError):
                        pass
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

                # If done tool, extract results
                if tool_name == "done":
                    done_summary = tool_args.get("summary", "")
                    test_passed = _extract_test_passed(done_summary, had_execution_errors)
                    test_results = [{"summary": done_summary}]
                    messages.append({"role": "assistant", "name": "tester",
                                     "content": done_summary})

                    return {
                        "test_passed": test_passed,
                        "test_results": test_results,
                        "messages": messages,
                    }

        # Exited loop without calling done
        messages.append({"role": "assistant", "name": "tester",
                         "content": done_summary or "测试完成（未调用 done 工具）"})

        return {
            "test_passed": test_passed,
            "test_results": test_results,
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"Tester error: {type(e).__name__}: {e}")
        return {
            "error": str(e),
            "test_passed": False,
            "messages": messages + [{"role": "assistant", "name": "tester",
                                      "content": f"测试失败：{str(e)[:200]}"}],
        }
