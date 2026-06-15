"""Architect Agent module.

Responsible for designing technical architecture based on user stories and features.
"""
import json
from typing import Any

from devteam.agents.schemas import ArchitectOutput
from devteam.utils.json_parser import extract_json
from devteam.utils.llm import call_llm_async

# ── Prompts ──────────────────────────────────────────────────────────────────

ARCHITECT_SYSTEM_PROMPT = """你是系统架构师，擅长技术选型和架构设计。

## 推理策略（按顺序执行）
1. 【约束识别】先识别技术约束：语言、框架、部署环境、性能要求
2. 【方案设计】提出最合理的架构方案，说明为什么选这个
3. 【模块划分】将系统拆分为独立模块，每个模块职责单一
4. 【接口设计】API 定义必须完整：method/path/request/response
5. 【自审】接口是否清晰？有没有遗漏的边界情况？

## 常见错误（避免）
❌ 过度设计（如为简单计算器设计微服务架构）
❌ API 只写了 path 没写 request/response

## 输出要求
- 严格按照 JSON schema 输出，不要添加其他文字

请用以下JSON格式输出：
{
    "architecture_description": "架构描述",
    "tech_stack": {"backend": "FastAPI", "database": "SQLite", ...},
    "modules": ["模块1", "模块2", ...],
    "api_definitions": [
        {"method": "GET", "path": "/api/xxx", "description": "...", "request_body": null, "response_body": {...}}
    ],
    "data_models": [
        {"name": "ModelName", "fields": {"field1": "type1", "field2": "type2"}, "relationships": []}
    ]
}

## 错误恢复
如果你收到"上一次执行失败"的提示，先理解错误原因，不要重复同样的操作。"""

ARCHITECT_CRITIC_PROMPT = """你是架构审查专家。从以下角度审查架构设计：

【扩展性】
- 架构是否支持未来扩展？
- 模块划分是否合理？

【性能】
- 有没有性能瓶颈？
- 数据库设计是否合理？

【安全】
- 有没有安全风险？
- API是否有鉴权？

【完整性】
- API定义是否完整？
- 数据模型是否覆盖所有需求？

请用JSON格式回复：
{"approved": true/false, "issues": ["问题1", ...], "suggestion": "修改建议"}
如果架构没有问题，approved设为true，issues留空数组。"""


# ── Helper Functions ─────────────────────────────────────────────────────────

def build_architect_prompt(state: dict) -> list[dict]:
    """Build LLM messages for architect agent.

    Args:
        state: Current ProjectState dict

    Returns:
        List of message dicts for LLM
    """
    messages = [
        {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
    ]

    # Build user message with user stories and features
    user_stories = state.get("user_stories", [])
    features = state.get("features", [])
    requirement = state.get("requirement", "")

    user_content = f"用户需求：{requirement}\n\n"
    user_content += "用户故事：\n"
    for story in user_stories:
        user_content += f"- {story.get('id', '')}: {story.get('title', '')} - {story.get('description', '')}\n"

    if features:
        user_content += "\n功能清单：\n"
        for feature in features:
            user_content += f"- {feature.get('name', '')}: {feature.get('description', '')}\n"

    # Add user feedback if present (rethink mechanism)
    user_feedback = state.get("user_feedback")
    if user_feedback:
        user_content += f"\n用户反馈：{user_feedback}\n请根据反馈改进架构设计。"

    # 注入上一次的错误信息（重试时 LLM 能看到错在哪）
    prev_error = state.get("error")
    if prev_error:
        user_content += f"\n\n⚠️ 上一次执行失败，错误：{prev_error[:500]}\n请避免重复同样的错误。"

    messages.append({"role": "user", "content": user_content})

    return messages


# ── Agent Node ──────────────────────────────────────────────────────────────

async def architect_agent(state: dict) -> dict[str, Any]:
    """Architect agent node: design technical architecture.

    Uses Proposer-Critic pattern when enabled.

    Args:
        state: Current ProjectState dict

    Returns:
        State update dict with architecture, api_definitions, data_models
    """
    from devteam.agents.discussion import get_discussion_config, proposer_critic_discuss
    from devteam.utils.guard import check_injection

    messages = list(state.get("messages", []))

    # 注入检测：检查用户反馈是否包含恶意内容
    user_feedback = state.get("user_feedback", "")
    if user_feedback and check_injection(user_feedback):
        return {
            "error": "用户反馈包含可疑内容",
            "messages": messages + [{"role": "assistant", "name": "architect",
                                      "content": "检测到可疑输入，已拒绝处理。"}],
        }
    discussion_config = get_discussion_config().get("architect", {})

    try:
        # Build prompt
        arch_messages = build_architect_prompt(state)
        task = arch_messages[-1]["content"]

        # Use Proposer-Critic if enabled
        if discussion_config.get("enabled", False):
            raw_response, discussion = await proposer_critic_discuss(
                task=task,
                proposer_prompt=ARCHITECT_SYSTEM_PROMPT,
                critic_prompt=ARCHITECT_CRITIC_PROMPT,
                max_rounds=discussion_config.get("max_rounds", 3),
                mode=discussion_config.get("mode", "full"),
            )
            # Record discussion
            for round_data in discussion:
                messages.append({"role": "assistant", "name": "arch_proposer",
                                 "content": round_data["proposal"]})
                critique = round_data["critique"]
                critique_text = f"approved={critique['approved']}"
                if critique.get("issues"):
                    critique_text += f", issues={critique['issues']}"
                messages.append({"role": "assistant", "name": "arch_critic",
                                 "content": critique_text})
        else:
            raw_response = await call_llm_async(arch_messages)

        # Extract and parse JSON
        json_str = extract_json(raw_response)
        parsed = json.loads(json_str)

        # Validate with Pydantic schema
        output = ArchitectOutput(**parsed)

        return {
            "architecture": {
                "description": output.architecture_description,
                "tech_stack": output.tech_stack,
                "modules": output.modules,
            },
            "api_definitions": [api.model_dump() for api in output.api_definitions],
            "data_models": [model.model_dump() for model in output.data_models],
            "current_agent": "developer",
            "error": None,  # 清除旧 error
            "messages": messages + [{"role": "assistant", "name": "architect",
                                      "content": f"架构设计完成，定义了 {len(output.api_definitions)} 个API和 {len(output.data_models)} 个数据模型"}],
        }

    except json.JSONDecodeError:
        return {
            "error": "无法解析LLM响应为JSON格式",
            "current_agent": "architect",
            "_architect_retry_count": state.get("_architect_retry_count", 0) + 1,
            "messages": messages + [{"role": "assistant", "name": "architect",
                                      "content": "架构设计失败：无法解析LLM响应"}],
        }
    except Exception as e:
        return {
            "error": str(e),
            "current_agent": "architect",
            "_architect_retry_count": state.get("_architect_retry_count", 0) + 1,
            "messages": messages + [{"role": "assistant", "name": "architect",
                                      "content": f"架构设计失败：{str(e)}"}],
        }
