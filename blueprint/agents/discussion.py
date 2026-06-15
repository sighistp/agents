"""Proposer-Critic discussion module.

Implements the dual-agent adversarial review pattern for quality assurance.
All LLM calls are async to avoid blocking the event loop.
"""
import json
import logging
from pathlib import Path
from typing import Any

from blueprint.utils.json_parser import extract_json
from blueprint.utils.llm import call_llm_async

logger = logging.getLogger(__name__)

# ── Discussion Configuration ─────────────────────────────────────────────────

def _get_discussion_config() -> dict:
    """Get discussion config. Reads from data/settings.json first, falls back to config.py."""
    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    is_max_mode = False

    if settings_file.exists():
        try:
            ui_settings = json.loads(settings_file.read_text(encoding="utf-8"))
            is_max_mode = ui_settings.get("agent_mode", "mini") == "max"
        except (json.JSONDecodeError, IOError):
            pass
    else:
        from blueprint.config import settings
        is_max_mode = settings.agent_mode == "max"

    return {
        "pm": {"enabled": is_max_mode, "max_rounds": 1, "mode": "full"},
        "architect": {"enabled": is_max_mode, "max_rounds": 1, "mode": "full"},
        "developer": {"enabled": is_max_mode, "max_rounds": 1, "mode": "post_review"},
        "tester": {"enabled": False},
        "reviewer": {"enabled": False},
    }


def get_discussion_config() -> dict:
    return _get_discussion_config()


DISCUSSION_CONFIG = _get_discussion_config()


# ── Helper Functions ─────────────────────────────────────────────────────────

def _parse_critic_result(raw: str) -> dict:
    """Parse critic response into structured result."""
    try:
        json_str = extract_json(raw)
        parsed = json.loads(json_str)
        return {
            "approved": parsed.get("approved", False),
            "issues": parsed.get("issues", parsed.get("critical_issues", [])),
            "suggestion": parsed.get("suggestion", ""),
        }
    except (json.JSONDecodeError, AttributeError):
        return {
            "approved": False,
            "issues": ["Failed to parse critic response"],
            "suggestion": raw,
        }


# ── Main Discussion Function (async) ────────────────────────────────────────

async def proposer_critic_discuss(
    task: str,
    proposer_prompt: str,
    critic_prompt: str,
    max_rounds: int = 3,
    mode: str = "full",
) -> tuple[str, list[dict]]:
    """Run Proposer-Critic discussion loop (async).

    Args:
        task: The task description for the proposer
        proposer_prompt: System prompt for the proposer
        critic_prompt: System prompt for the critic
        max_rounds: Maximum number of discussion rounds
        mode: "full" or "post_review"

    Returns:
        Tuple of (final_result, discussion_log)
    """
    discussion_log = []

    try:
        if mode == "full":
            proposal = await call_llm_async([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])

            for round_num in range(max_rounds):
                critic_raw = await call_llm_async([
                    {"role": "system", "content": critic_prompt + '\n\n请用JSON格式回复：\n{"approved": true/false, "issues": [...], "suggestion": "..."}'},
                    {"role": "user", "content": f"请审查以下方案：\n\n{proposal}"},
                ])
                critique = _parse_critic_result(critic_raw)

                discussion_log.append({
                    "round": round_num + 1,
                    "proposal": proposal,
                    "critique": critique,
                })

                if critique["approved"]:
                    break
                if round_num == max_rounds - 1:
                    break

                proposal = await call_llm_async([
                    {"role": "system", "content": proposer_prompt},
                    {"role": "user", "content": f"原方案：\n{proposal}\n\n审查反馈：\n{critique['suggestion']}\n\n请根据反馈修改方案。"},
                ])

            return proposal, discussion_log

        elif mode == "post_review":
            result = await call_llm_async([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])

            critic_raw = await call_llm_async([
                {"role": "system", "content": critic_prompt + '\n\n请用JSON格式回复：\n{"approved": true/false, "critical_issues": [...], "suggestions": [...]}'},
                {"role": "user", "content": f"请审查：\n\n{result}"},
            ])
            critique = _parse_critic_result(critic_raw)

            discussion_log.append({"round": 1, "proposal": result, "critique": critique})

            if not critique["approved"] and critique["issues"]:
                result = await call_llm_async([
                    {"role": "system", "content": proposer_prompt},
                    {"role": "user", "content": f"原结果：\n{result}\n\n关键问题：\n{critique['issues']}\n\n请修复这些问题。"},
                ])

            return result, discussion_log

        else:
            result = await call_llm_async([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])
            return result, discussion_log

    except Exception as e:
        logger.error(f"Proposer-Critic discussion failed: {e}")
        raise
