"""Tester Agent module.

Responsible for running tests using a tool-calling loop.
Uses file_read and execute_python tools — no file_write.
"""
import json
import time
from typing import Any

from blueprint.agents.tools import TESTER_TOOLS, serialize_call, get_call_name, get_call_args
from blueprint.agents.tool_executor import execute_tool
import asyncio
from blueprint.utils.llm import call_llm_with_tools_async
from blueprint.utils.logger import get_logger
from blueprint.utils.trace_db import TraceDB

logger = get_logger("tester")

# ── Prompts ──────────────────────────────────────────────────────────────────

TESTER_SYSTEM_PROMPT = """你是测试工程师，负责对项目代码进行测试。

## 测试策略
1. 先用 file_read 读取代码，理解逻辑
2. 设计测试用例：正常路径 + 边界条件 + 异常情况
3. 用 execute_python 逐个执行测试
4. 汇总结果，调用 done 提交报告

## 输出规范
测试通过时：
done(summary="3 passed, 0 failed: 加法测试通过, 减法测试通过, 除零测试通过")

测试失败时（必须给出修复建议）：
done(summary="2 passed, 1 failed: division(1,0) 返回 None 而非抛出异常，建议在 division 中加 if b==0: raise ValueError('除数不能为零')")

## 错误恢复
如果你收到"上一次执行失败"的提示，先理解错误原因，不要重复同样的操作。

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

    # 注入上一次的错误信息
    prev_error = state.get("error")
    if prev_error:
        user_content += f"\n\n⚠️ 上一次执行失败，错误：{prev_error[:500]}\n请避免重复同样的错误。"

    user_content += "\n请开始测试。先用 file_read 查看代码，再用 execute_python 执行测试。"
    messages.append({"role": "user", "content": user_content})

    return messages


def _extract_test_passed(summary: str, had_execution_errors: bool) -> bool:
    """Extract test result using structured regex parsing."""
    if had_execution_errors:
        return False

    import re
    summary_lower = summary.lower()

    passed_match = re.search(r'(\d+)\s*passed', summary_lower)
    failed_match = re.search(r'(\d+)\s*failed', summary_lower)
    error_match = re.search(r'(\d+)\s*error', summary_lower)

    if failed_match and int(failed_match.group(1)) > 0:
        return False
    if error_match and int(error_match.group(1)) > 0:
        return False
    if passed_match and int(passed_match.group(1)) > 0:
        return True

    pass_keywords = ["全部通过", "all passed", "all tests passed",
                     "0 fail", "0 error", "0失败", "0 failed"]
    for kw in pass_keywords:
        if kw in summary_lower:
            return True

    return True


# ── Agent Node ──────────────────────────────────────────────────────────────

async def tester_agent(state: dict) -> dict[str, Any]:
    """Tester agent: tool-loop based testing.

    Iterates up to MAX_STEPS, calling LLM with tools and executing them.
    Returns state update with test_passed, test_results, messages.
    """
    messages = list(state.get("messages", []))
    collected_files = state.get("files", {})
    project_dir = state.get("project_dir", ".")
    start_time = time.time()
    all_tool_calls: list = []

    try:
        logger.info(f"Tester started, files: {list(state.get('files', {}).keys())}")
        # Build initial conversation
        llm_messages = build_tester_messages(state)

        test_passed = False
        test_results = []
        done_summary = ""
        had_execution_errors = False  # Track if any execute_python failed

        for step in range(MAX_STEPS):
            # Call LLM with tools
            response = await call_llm_with_tools_async(llm_messages, TESTER_TOOLS)

            # Record assistant message
            assistant_msg = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = [serialize_call(tc) for tc in response.tool_calls]
            llm_messages.append(assistant_msg)

            # If no tool calls, treat as done
            if not response.tool_calls:
                messages.append({"role": "assistant", "name": "tester",
                                 "content": response.content or "测试完成"})
                # Record trace for implicit done
                try:
                    trace_db = TraceDB()
                    trace_db.save(
                        project_id=state.get("project_id", ""),
                        agent="tester",
                        iteration=state.get("iteration", 0),
                        prompt=llm_messages[1]["content"][:2000] if len(llm_messages) > 1 else "",
                        response=str(response.content or "")[:2000],
                        tools_called=all_tool_calls,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                except Exception:
                    pass
                break

            # Execute each tool call
            for tc in response.tool_calls:
                tool_name = get_call_name(tc)
                all_tool_calls.append(tool_name)
                tool_args = get_call_args(tc)
                tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id

                # Execute the tool
                result_str = await asyncio.to_thread(execute_tool, tc, project_dir)

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
                    logger.info(f"Tester done: test_passed={test_passed}, summary={done_summary[:80]}")

                    # Record trace (failure doesn't affect main flow)
                    try:
                        trace_db = TraceDB()
                        trace_db.save(
                            project_id=state.get("project_id", ""),
                            agent="tester",
                            iteration=state.get("iteration", 0),
                            prompt=llm_messages[1]["content"][:2000] if len(llm_messages) > 1 else "",
                            response=str(llm_messages[-1].get("content", ""))[:2000] if llm_messages else "",
                            tools_called=all_tool_calls,
                            duration_ms=int((time.time() - start_time) * 1000),
                        )
                    except Exception:
                        pass
                    return {
                        "test_passed": test_passed,
                        "test_results": test_results,
                        "error": None,  # 清除旧 error
                        "_tester_retry_count": 0,
                        "messages": messages,
                    }

        # Exited loop without calling done
        messages.append({"role": "assistant", "name": "tester",
                         "content": done_summary or "测试完成（未调用 done 工具）"})

        # Record trace (failure doesn't affect main flow)
        try:
            trace_db = TraceDB()
            trace_db.save(
                project_id=state.get("project_id", ""),
                agent="tester",
                iteration=state.get("iteration", 0),
                prompt=llm_messages[1]["content"][:2000] if len(llm_messages) > 1 else "",
                response=str(llm_messages[-1].get("content", ""))[:2000] if llm_messages else "",
                tools_called=all_tool_calls,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception:
            pass
        return {
            "test_passed": test_passed,
            "test_results": test_results,
            "error": None,  # 清除旧 error
            "_tester_retry_count": 0,
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"Tester error: {type(e).__name__}: {e}")
        logger.info(f"Tester finished with error, test_passed=False")
        return {
            "error": str(e),
            "test_passed": False,
            "_tester_retry_count": state.get("_tester_retry_count", 0) + 1,
            "test_results": [{"summary": f"测试异常：{str(e)[:200]}", "status": "error"}],
            "messages": messages + [{"role": "assistant", "name": "tester",
                                      "content": f"测试失败：{str(e)[:200]}"}],
        }
