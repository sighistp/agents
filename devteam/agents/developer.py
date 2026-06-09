"""Developer Agent module — tool-loop pattern.

Uses LLM function-calling in a loop (max 10 steps).
Each step: call LLM with tools → execute tool_calls → feed results back.
Terminates when the LLM calls `done` or stops calling tools (implicit done).
"""
import json
from typing import Any

from devteam.agents.tools import DEVELOPER_TOOLS, serialize_call, get_call_name, get_call_args
from devteam.agents import tool_executor
from devteam.utils.llm import call_llm_with_tools
from devteam.utils.logger import get_logger

logger = get_logger("developer")

# ── Prompts ──────────────────────────────────────────────────────────────────

DEVELOPER_SYSTEM_PROMPT = """你是高级程序员。使用提供的工具来完成任务。

规则：
- 使用 file_write 工具写入文件
- 使用 file_read 工具读取已有文件
- 使用 execute_python 工具执行代码验证
- 使用 done 工具标记任务完成，并提供 summary 和 key_decisions
- 逐步完成，不要一次输出所有内容"""

DEVELOPER_CRITIC_PROMPT = """你是代码审查专家。只标记会导致崩溃的critical问题。
不要纠结代码风格。只关注：安全漏洞、逻辑错误、未捕获异常。
请用JSON格式回复：
{{"approved": true/false, "critical_issues": ["问题1", ...]}}"""

MAX_STEPS = 10


# ── Helper Functions ─────────────────────────────────────────────────────────

def build_developer_prompt(state: dict) -> list[dict]:
    """Build initial LLM messages for developer agent."""
    messages = [{"role": "system", "content": DEVELOPER_SYSTEM_PROMPT}]

    requirement = state.get("requirement", "")
    architecture = state.get("architecture", {})
    api_definitions = state.get("api_definitions", [])
    data_models = state.get("data_models", [])
    iteration = state.get("iteration", 0)

    user_content = f"需求：{requirement}\n"
    if architecture:
        user_content += f"架构：{json.dumps(architecture, ensure_ascii=False)}\n"
    if api_definitions:
        user_content += "API：\n"
        for api in api_definitions:
            user_content += f"- {api.get('method', 'GET')} {api.get('path', '')}: {api.get('description', '')}\n"
    if data_models:
        user_content += "数据模型：\n"
        for model in data_models:
            user_content += f"- {model.get('name', '')}: {json.dumps(model.get('fields', {}), ensure_ascii=False)}\n"
    user_content += f"迭代：第{iteration + 1}次\n"

    user_feedback = state.get("user_feedback")
    if user_feedback:
        user_content += f"用户反馈：{user_feedback}\n"

    messages.append({"role": "user", "content": user_content})
    return messages


# ── Agent Node ──────────────────────────────────────────────────────────────

def developer_agent(state: dict) -> dict[str, Any]:
    """Developer agent: tool-loop pattern.

    Each iteration calls LLM with tools, executes the returned tool_calls,
    feeds results back, and repeats until `done` is called or no tool_calls
    are returned (implicit done), or MAX_STEPS is exceeded.
    """
    messages = build_developer_prompt(state)
    project_dir = state.get("project_dir", ".")
    files_written: dict[str, str] = {}
    key_decisions: list[str] = []

    try:
        for step in range(MAX_STEPS):
            # 1. Call LLM with tools
            response = call_llm_with_tools(messages, DEVELOPER_TOOLS)

            # Build assistant message with tool_calls in OpenAI format
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = [serialize_call(tc) for tc in response.tool_calls]
            messages.append(assistant_msg)

            # 2. No tool calls → implicit done
            if not response.tool_calls:
                logger.info("LLM returned no tool calls, treating as implicit done")
                break

            # 3. Execute each tool call and append results
            for tc in response.tool_calls:
                tool_name = get_call_name(tc)
                tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id
                result_str = tool_executor.execute_tool(tc, project_dir)

                # Track file_write calls
                if tool_name == "file_write":
                    try:
                        args = get_call_args(tc)
                        path = args.get("path", "")
                        content = args.get("content", "")
                        result_data = json.loads(result_str)
                        if result_data.get("success"):
                            files_written[path] = content
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Track done tool
                if tool_name == "done":
                    try:
                        args = get_call_args(tc)
                        if args.get("key_decisions"):
                            key_decisions.extend(args["key_decisions"])
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Append tool result message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

            # 4. If done was called, exit loop
            if any(get_call_name(tc) == "done" for tc in response.tool_calls):
                break

        else:
            # Exhausted MAX_STEPS without done
            return {
                "files": files_written,
                "iteration": state.get("iteration", 0) + 1,
                "key_decisions": key_decisions,
                "error": "超过最大步数（10步），任务未正常完成",
                "messages": messages,
            }

        return {
            "files": files_written,
            "iteration": state.get("iteration", 0) + 1,
            "key_decisions": key_decisions,
            "_developer_retry_count": 0,  # 成功后重置重试计数
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"Developer error: {type(e).__name__}: {e}")
        return {
            "files": files_written,
            "iteration": state.get("iteration", 0) + 1,
            "key_decisions": key_decisions,
            "error": str(e),
            "messages": messages,
        }
