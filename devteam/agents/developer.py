"""Developer Agent module — tool-loop pattern.

Uses LLM function-calling in a loop (max 5 steps).
Each step: call LLM with tools → execute tool_calls → feed results back.
Terminates when the LLM calls `done` or stops calling tools (implicit done).
"""
import json
from typing import Any

from devteam.agents.tools import DEVELOPER_TOOLS, serialize_call, get_call_name, get_call_args
from devteam.agents import tool_executor
import asyncio
from devteam.utils.llm import call_llm_with_tools_async
from devteam.utils.logger import get_logger
from devteam.utils.memory import get_memory

logger = get_logger("developer")

# ── Prompts ──────────────────────────────────────────────────────────────────

DEVELOPER_SYSTEM_PROMPT = """你是高级程序员。使用提供的工具来完成任务。

## 每轮决策框架
每轮调用工具前，先想：
1. 我现在需要什么？（读文件？写文件？验证？）
2. 这个工具调用能推进任务吗？
3. 调用后我怎么判断成功/失败？

## 工具使用策略
1. 先用 file_read 了解现有代码（如果有）
2. 用 file_write 逐个写入文件，一次写一个，不要一次全写完
3. 用 execute_python 验证代码能运行
4. 全部完成后用 done 提交

## 项目结构约束
- 每个项目只用一种目录结构，不要同时写 backend/+frontend/ 和 src/+public/ 两套
- Python Web 项目：main.py 在根目录，静态文件在 static/ 下
- 前端项目：HTML（结构）+ CSS（样式）+ JS（逻辑）分开写，不要全塞一个文件
- 不要创建重复文件
- 文件数量控制在 10 个以内
- 每个文件职责单一

## 常见错误（避免）
❌ 所有代码塞在一个 HTML 文件里不拆分
❌ 写完文件不验证就调 done
❌ 文件路径写错（如 absolute path 或含 ..）

## 错误恢复
如果你收到"上一次执行失败"的提示，先理解错误原因，不要重复同样的操作。"""

DEVELOPER_CRITIC_PROMPT = """你是代码审查专家。只标记会导致崩溃的critical问题。
不要纠结代码风格。只关注：安全漏洞、逻辑错误、未捕获异常。
请用JSON格式回复：
{{"approved": true/false, "critical_issues": ["问题1", ...]}}"""

MAX_STEPS = 8


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

    # 从 SQLite 记忆层获取之前的执行上下文
    project_id = state.get("project_id", "")
    if project_id and iteration > 0:
        try:
            memory_context = get_memory().get_developer_context(project_id, iteration)
            if memory_context:
                user_content += f"\n{memory_context}\n"
        except Exception:
            pass  # 记忆读取失败不影响主流程

    # 注入上一次的错误信息（重试时 LLM 能看到错在哪）
    prev_error = state.get("error")
    if prev_error:
        user_content += f"\n⚠️ 上次失败：{prev_error[:200]}\n"

    user_feedback = state.get("user_feedback")
    if user_feedback:
        user_content += f"用户反馈：{user_feedback}\n"

    # 上一轮测试反馈（精简版，只给关键信息）
    test_results = state.get("test_results")
    if test_results and not state.get("test_passed", True):
        if isinstance(test_results, list) and len(test_results) > 0:
            latest = test_results[0] if isinstance(test_results[0], dict) else {}
            summary = latest.get('summary', str(test_results[0]))[:300]
        elif isinstance(test_results, dict):
            summary = test_results.get('summary', str(test_results))[:300]
        else:
            summary = ""
        if summary:
            user_content += f"\n测试反馈：{summary}\n"

    # 上一轮审查反馈（精简版，只给 suggestion）
    review_comments = state.get("review_comments")
    if review_comments and not state.get("review_approved", True):
        suggestions = []
        for c in (review_comments if isinstance(review_comments, list) else [])[:3]:
            if isinstance(c, dict) and c.get('suggestion'):
                suggestions.append(c['suggestion'])
        if suggestions:
            user_content += f"\n审查建议：{'；'.join(suggestions)}\n"

    messages.append({"role": "user", "content": user_content})
    return messages


# ── Agent Node ──────────────────────────────────────────────────────────────

async def developer_agent(state: dict) -> dict[str, Any]:
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
            response = await call_llm_with_tools_async(messages, DEVELOPER_TOOLS)

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
            this_round_new_writes = 0
            for tc in response.tool_calls:
                tool_name = get_call_name(tc)
                tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id
                result_str = await asyncio.to_thread(tool_executor.execute_tool, tc, project_dir)

                # Track file_write calls
                if tool_name == "file_write":
                    try:
                        args = get_call_args(tc)
                        path = args.get("path", "")
                        content = args.get("content", "")
                        result_data = json.loads(result_str)
                        if result_data.get("success"):
                            files_written[path] = content
                            this_round_new_writes += 1
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

            # 5. 隐式完成：已写过文件 + 本轮没新写入 → LLM 做完了
            #    典型：第1轮写文件，第2轮测试/读取/无操作 → 保存
            if files_written and this_round_new_writes == 0:
                logger.info(f"Files written ({len(files_written)}), no new writes → implicit done at step {step}")
                break

        else:
            # Exhausted MAX_STEPS without done
            return {
                "files": files_written,
                "iteration": state.get("iteration", 0) + 1,
                "key_decisions": key_decisions,
                "error": f"超过最大步数（{MAX_STEPS}步），任务未正常完成",
                "_developer_retry_count": state.get("_developer_retry_count", 0) + 1,
                "messages": messages,
            }

        # 如果 LLM 没写任何文件，标记为错误（防止 Tester 空转死循环）
        if not files_written:
            return {
                "files": files_written,
                "iteration": state.get("iteration", 0) + 1,
                "key_decisions": key_decisions,
                "error": "Developer 未生成任何文件，需求可能不明确",
                "_developer_retry_count": state.get("_developer_retry_count", 0) + 1,
                "messages": messages,
            }

        return {
            "files": files_written,
            "iteration": state.get("iteration", 0) + 1,
            "key_decisions": key_decisions,
            "error": None,  # 清除旧 error，否则路由函数一直看到残留值
            "test_passed": True,  # 重置上一轮的失败标志
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
            "_developer_retry_count": state.get("_developer_retry_count", 0) + 1,
            "messages": messages,
        }
