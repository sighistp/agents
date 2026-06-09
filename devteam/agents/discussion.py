"""Proposer-Critic discussion module.

Implements the dual-agent adversarial review pattern for quality assurance.
"""
import json
import logging
from pathlib import Path
from typing import Any

from devteam.utils.json_parser import extract_json
from devteam.utils.llm import call_llm

logger = logging.getLogger(__name__)

# ── Discussion Configuration ─────────────────────────────────────────────────

def _get_discussion_config() -> dict:
    """Get discussion config. Reads from data/settings.json (UI settings) first, falls back to config.py."""
    # Try reading from UI settings file (settings page saves here)
    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    is_max_mode = False

    if settings_file.exists():
        try:
            ui_settings = json.loads(settings_file.read_text(encoding="utf-8"))
            is_max_mode = ui_settings.get("agent_mode", "mini") == "max"
        except (json.JSONDecodeError, IOError):
            pass
    else:
        # Fallback to config.py
        from devteam.config import settings
        is_max_mode = settings.agent_mode == "max"

    return {
        "pm": {
            "enabled": is_max_mode,
            "max_rounds": 1,
            "mode": "full",
        },
        "architect": {
            "enabled": is_max_mode,
            "max_rounds": 1,
            "mode": "full",
        },
        "developer": {
            "enabled": is_max_mode,
            "max_rounds": 1,
            "mode": "post_review",
        },
        "tester": {
            "enabled": False,
        },
        "reviewer": {
            "enabled": False,
        },
    }


# Dynamic config - re-reads from settings file each time
# Use get_discussion_config() instead of DISCUSSION_CONFIG for fresh values
def get_discussion_config() -> dict:
    """Get fresh discussion config (reads from settings file each call)."""
    return _get_discussion_config()


# For backward compatibility (snapshot at import time)
DISCUSSION_CONFIG = _get_discussion_config()


# ── Helper Functions ─────────────────────────────────────────────────────────


def _parse_critic_result(raw: str) -> dict:
    """Parse critic response into structured result.

    Args:
        raw: Raw LLM response

    Returns:
        Dict with approved, issues, suggestion
    """
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


# ── Main Discussion Function ────────────────────────────────────────────────

def proposer_critic_discuss(
    task: str,
    proposer_prompt: str,
    critic_prompt: str,
    max_rounds: int = 3,
    mode: str = "full",
) -> tuple[str, list[dict]]:
    """Run Proposer-Critic discussion loop.

    Args:
        task: The task description for the proposer
        proposer_prompt: System prompt for the proposer
        critic_prompt: System prompt for the critic
        max_rounds: Maximum number of discussion rounds
        mode: "full" (Proposer-Critic loop) or "post_review" (generate then review once)

    Returns:
        Tuple of (final_result, discussion_log)
        - final_result: The final output string
        - discussion_log: List of dicts with 'round', 'proposal', 'critique'
    """
    discussion_log = []

    try:
        if mode == "full":
            # Full mode: Proposer → Critic loop
            proposal = call_llm([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])

            for round_num in range(max_rounds):
                # Critic reviews
                critic_raw = call_llm([
                    {"role": "system", "content": critic_prompt + "\n\n请用JSON格式回复：\n{\"approved\": true/false, \"issues\": [...], \"suggestion\": \"...\"}"},
                    {"role": "user", "content": f"请审查以下方案：\n\n{proposal}"},
                ])
                critique = _parse_critic_result(critic_raw)

                discussion_log.append({
                    "round": round_num + 1,
                    "proposal": proposal,
                    "critique": critique,
                })

                # If approved, stop
                if critique["approved"]:
                    break

                # Last round, don't modify
                if round_num == max_rounds - 1:
                    break

                # Proposer revises based on feedback
                proposal = call_llm([
                    {"role": "system", "content": proposer_prompt},
                    {"role": "user", "content": f"原方案：\n{proposal}\n\n审查反馈：\n{critique['suggestion']}\n\n请根据反馈修改方案。"},
                ])

            return proposal, discussion_log

        elif mode == "post_review":
            # Post-review mode: generate → review → fix if critical
            result = call_llm([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])

            # Critic reviews once
            critic_raw = call_llm([
                {"role": "system", "content": critic_prompt + "\n\n请用JSON格式回复：\n{\"approved\": true/false, \"critical_issues\": [...], \"suggestions\": [...]}"},
                {"role": "user", "content": f"请审查：\n\n{result}"},
            ])
            critique = _parse_critic_result(critic_raw)

            discussion_log.append({
                "round": 1,
                "proposal": result,
                "critique": critique,
            })

            # If has critical issues, fix once
            if not critique["approved"] and critique["issues"]:
                result = call_llm([
                    {"role": "system", "content": proposer_prompt},
                    {"role": "user", "content": f"原结果：\n{result}\n\n关键问题：\n{critique['issues']}\n\n请修复这些问题。"},
                ])

            return result, discussion_log

        else:
            # Unknown mode, just run proposer once
            result = call_llm([
                {"role": "system", "content": proposer_prompt},
                {"role": "user", "content": task},
            ])
            return result, discussion_log

    except Exception as e:
        # Log error and re-raise for proper error handling upstream
        logger.error(f"Proposer-Critic discussion failed: {e}")
        raise
