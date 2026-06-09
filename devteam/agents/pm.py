"""PM (Product Manager) Agent module.

Responsible for analyzing user requirements and producing structured
user stories, features, and technical constraints.
"""
import json

from langgraph.types import interrupt

from devteam.agents.schemas import PMOutput
from devteam.agents.state import ProjectState
from devteam.utils.guard import check_injection
from devteam.utils.json_parser import extract_json
from devteam.utils.llm import call_llm_async
from devteam.utils.logger import get_logger

logger = get_logger("pm")

# ── Prompts ─────────────────────────────────────────────────────────────

PM_SYSTEM_PROMPT = """你是资深产品经理，负责分析用户需求并产出结构化的产品规格。

## 你的职责
- 分析用户需求，拆解为清晰、可执行的用户故事
- 识别满足用户需求的关键功能
- 记录技术约束和假设
- 只有在需求真正模糊时才要求澄清

## 推理策略
1. 理解用户要解决的核心问题
2. 识别系统的关键用户角色
3. 将需求拆解为用户故事（谁、什么、为什么）
4. 将相关故事归组为功能
5. 识别技术约束（性能、安全、兼容性）
6. 判断是否有足够信息继续

## 输出格式
必须用以下JSON格式输出：
{
    "user_stories": [
        {
            "id": "US-001",
            "title": "简短描述性标题",
            "description": "作为[角色]，我想要[功能]，以便[收益]",
            "acceptance_criteria": ["假设X，当Y时，则Z"],
            "priority": "high|medium|low"
        }
    ],
    "features": [
        {
            "name": "功能名称",
            "description": "功能描述",
            "priority": "high|medium|low",
            "related_stories": ["US-001"]
        }
    ],
    "technical_constraints": ["约束1", "约束2"],
    "needs_clarification": false,
    "clarification_questions": []
}

重要规则：
- user_stories不能为空（至少一个故事）
- 每个用户故事必须有至少一个验收标准
- 只有需求真正模糊时才设 needs_clarification: true
- 如果用户需求明确（如"做一个计算器"），直接拆解，不要要求澄清
- 只输出JSON，不要添加其他文字"""


PM_CRITIC_PROMPT = """你是审查产品经理输出的批评者。

## 你的任务
审查PM的用户故事、功能和技术约束：
1. 完整性 - 故事是否完整覆盖需求？
2. 清晰性 - 验收标准是否具体可测试？
3. 一致性 - 功能是否正确映射到故事？
4. 可行性 - 故事是否可实现？
5. 遗漏 - 错误场景和边界条件是否覆盖？

## 输出格式
用JSON格式回复：
{
    "approved": true/false,
    "issues": [
        {
            "severity": "critical|warning|suggestion",
            "description": "问题描述",
            "suggestion": "修改建议"
        }
    ],
    "summary": "总体评估"
}

建设性但彻底。标记会阻碍开发的关键问题。"""


# ── Helper Functions ─────────────────────────────────────────────────────


def build_pm_prompt(state: ProjectState) -> list[dict]:
    """Build the LLM messages for the PM agent.

    Args:
        state: Current project state

    Returns:
        List of message dicts with 'role' and 'content'
    """
    messages = [
        {"role": "system", "content": PM_SYSTEM_PROMPT},
    ]

    # Build user message with requirement
    user_content = f"## Requirement\n{state['requirement']}"

    # Include user feedback if present (rethink mechanism)
    user_feedback = state.get("user_feedback")
    if user_feedback:
        user_content += f"\n\n## User Feedback (Previous Iteration)\n{user_feedback}"

    messages.append({"role": "user", "content": user_content})

    return messages


# ── Agent Node Function ─────────────────────────────────────────────────


async def pm_agent(state: ProjectState) -> dict:
    """PM agent node: analyze requirements and produce user stories.

    This is the async node function used in the LangGraph workflow.
    Uses Proposer-Critic pattern when enabled.

    Args:
        state: Current project state

    Returns:
        Dict with state updates (user_stories, features, etc.)
    """
    from devteam.agents.discussion import get_discussion_config, proposer_critic_discuss

    messages = list(state.get("messages", []))
    discussion_config = get_discussion_config().get("pm", {})

    # Guard: check for prompt injection in the requirement
    requirement = state.get("requirement", "")
    if check_injection(requirement):
        logger.warning("Injection detected in requirement: %s", requirement[:100])
        return {
            "error": "Input rejected: suspicious content detected",
            "user_stories": [],
            "features": [],
            "current_agent": "pm",
            "messages": messages + [{"role": "assistant", "name": "pm",
                                      "content": "输入被拒绝：检测到可疑内容"}],
        }

    logger.info("PM agent processing requirement for project: %s",
                state.get("project_id", "unknown"))

    try:
        # Build prompt
        pm_messages = build_pm_prompt(state)
        task = pm_messages[-1]["content"]  # User message is the task

        # Use Proposer-Critic if enabled
        if discussion_config.get("enabled", False):
            raw_response, discussion = await proposer_critic_discuss(
                task=task,
                proposer_prompt=PM_SYSTEM_PROMPT,
                critic_prompt=PM_CRITIC_PROMPT,
                max_rounds=discussion_config.get("max_rounds", 3),
                mode=discussion_config.get("mode", "full"),
            )
            # Record discussion in messages
            for round_data in discussion:
                messages.append({"role": "assistant", "name": "pm_proposer",
                                 "content": round_data["proposal"]})
                critique = round_data["critique"]
                critique_text = f"approved={critique['approved']}"
                if critique.get("issues"):
                    critique_text += f", issues={critique['issues']}"
                messages.append({"role": "assistant", "name": "pm_critic",
                                 "content": critique_text})
        else:
            # Direct LLM call without discussion
            raw_response = await call_llm_async(pm_messages)

        # Extract and parse JSON
        json_str = extract_json(raw_response)
        parsed = json.loads(json_str)

        # Validate with Pydantic schema
        pm_output = PMOutput(**parsed)

        # Build result dict (convert Pydantic models to dicts for state)
        result = {
            "user_stories": [story.model_dump() for story in pm_output.user_stories],
            "features": [feat.model_dump() for feat in pm_output.features],
            "technical_constraints": pm_output.technical_constraints,
            "current_agent": "architect",
            "error": None,
            "messages": messages + [{"role": "assistant", "name": "pm",
                                      "content": f"已拆分为 {len(pm_output.user_stories)} 个用户故事"}],
        }
        logger.info("PM produced %d user stories, %d features",
                     len(pm_output.user_stories), len(pm_output.features))

        # Add clarification info if needed
        if pm_output.needs_clarification:
            result["needs_clarification"] = True
            result["clarification_questions"] = pm_output.clarification_questions

            # Use interrupt to pause and wait for user clarification
            # Note: interrupt requires LangGraph context, will raise RuntimeError if called outside
            try:
                clarification = interrupt({
                    "type": "clarify",
                    "message": "需求不够明确，请补充以下信息",
                    "questions": pm_output.clarification_questions
                })

                # User provided clarification, re-analyze
                # Don't mutate state directly - create a copy for this analysis
                clarified_requirement = state["requirement"] + f"\n补充说明：{clarification}"
                clarified_state = {**state, "requirement": clarified_requirement}
                pm_messages = build_pm_prompt(clarified_state)
                raw_response = await call_llm_async(pm_messages)
                json_str = extract_json(raw_response)
                parsed = json.loads(json_str)
                pm_output = PMOutput(**parsed)

                # Update result with clarified data
                result = {
                    "user_stories": [story.model_dump() for story in pm_output.user_stories],
                    "features": [feat.model_dump() for feat in pm_output.features],
                    "technical_constraints": pm_output.technical_constraints,
                    "current_agent": "architect",
                    "error": None,
                    "messages": messages + [{"role": "assistant", "name": "pm",
                                              "content": f"需求澄清后，拆分为 {len(pm_output.user_stories)} 个用户故事"}],
                }
            except RuntimeError:
                # Outside LangGraph context, interrupt() raises RuntimeError
                # The result already has needs_clarification and questions set
                pass

        return result

    except json.JSONDecodeError as e:
        logger.error("PM failed to parse LLM response as JSON: %s", e)
        return {
            "error": f"PM agent failed to parse LLM response as JSON: {e}",
            "user_stories": [],
            "features": [],
            "current_agent": "pm",
            "_pm_retry_count": state.get("_pm_retry_count", 0) + 1,
            "messages": messages + [{"role": "assistant", "name": "pm",
                                      "content": f"需求分析失败：{e}"}],
        }
    except Exception as e:
        logger.error("PM agent error: %s: %s", type(e).__name__, e)
        return {
            "error": f"PM agent error: {type(e).__name__}: {e}",
            "_pm_retry_count": state.get("_pm_retry_count", 0) + 1,
            "user_stories": [],
            "features": [],
            "current_agent": "pm",
            "messages": messages + [{"role": "assistant", "name": "pm",
                                      "content": f"需求分析失败：{e}"}],
        }
