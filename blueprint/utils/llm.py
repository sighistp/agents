"""LLM call wrapper with retry and rate limiting (sync + async)."""
import asyncio
import functools
import json
import logging
import sys
import os
import threading
from pathlib import Path
from threading import Semaphore
from blueprint.utils.cost_tracker import record_cost

logger = logging.getLogger(__name__)

# Windows 编码修复
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Windows console reconfigure failed: %s", e, exc_info=True)

from langchain_openai import ChatOpenAI

# Retry decorator (local, no external dependency)
def retry(max_attempts=3, backoff_base=1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    import time
                    time.sleep(backoff_base * (2 ** attempt))
        return wrapper
    return decorator

# Rate limiter: max 5 concurrent LLM calls
_llm_semaphore = Semaphore(5)


def trim_messages(messages: list, max_messages: int = 20) -> list:
    """Trim messages to a sliding window, preserving system messages and recency.

    P1.7: Prevents quadratic token growth by capping conversation length.
    """
    if len(messages) <= max_messages:
        return list(messages)

    system_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
    non_system = [m for m in messages if not (isinstance(m, dict) and m.get("role") == "system")]

    remaining = max_messages - len(system_msgs) - 1  # -1 for summary placeholder
    if remaining < 1:
        remaining = 1
    recent = non_system[-remaining:]

    dropped = len(non_system) - len(recent)
    summary_msg = {"role": "system", "content": f"Earlier conversation summary: {dropped} earlier messages omitted."}

    return system_msgs + [summary_msg] + recent


def _load_web_settings() -> dict:
    """Load settings from web UI (data/settings.json)."""
    settings_file = Path(__file__).parent.parent / "data" / "settings.json"
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load web settings: %s", e, exc_info=True)
    return {}


def _create_llm() -> ChatOpenAI:
    """Create LLM instance with configuration from settings."""
    from blueprint.config import settings

    # Check web UI settings first, then fall back to config
    web_settings = _load_web_settings()

    # API key: try web UI settings → secure API key file → config
    api_key = web_settings.get("api_key")
    if not api_key:
        api_key_file = Path(__file__).parent.parent / "data" / ".api_key"
        if api_key_file.exists():
            try:
                api_key = api_key_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    if not api_key:
        api_key = settings.llm_api_key or settings.deepseek_api_key

    base_url = web_settings.get("base_url") or settings.llm_base_url or settings.deepseek_base_url
    model = web_settings.get("model") or settings.llm_model or settings.deepseek_model

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        request_timeout=120,
        max_retries=0,  # 禁用 SDK 自带重试，用我们自己的 retry 装饰器
    )


# Global LLM instance (lazy initialized, thread-safe)
_llm = None
_llm_lock = threading.Lock()
_last_settings_hash = None


def _get_llm() -> ChatOpenAI:
    """Get or create the global LLM instance (thread-safe).
    Recreates if settings have changed."""
    global _llm, _last_settings_hash

    # Check if settings changed (use json.dumps for deterministic hash)
    web_settings = _load_web_settings()
    # Include code-level config in hash to detect timeout/retry changes
    import hashlib
    code_config = f"timeout=120,retries=0"
    current_hash = hashlib.md5(
        (json.dumps(web_settings, sort_keys=True) + code_config).encode()
    ).hexdigest()

    if _llm is None or current_hash != _last_settings_hash:
        with _llm_lock:
            if _llm is None or current_hash != _last_settings_hash:
                _llm = _create_llm()
                _last_settings_hash = current_hash
    return _llm


@retry(max_attempts=2, backoff_base=0.5)
def call_llm(messages: list) -> str:
    llm = _get_llm()
    with _llm_semaphore:
        response = llm.invoke(messages)
        record_cost(response)
        return response.content


# Module-level async semaphore for rate limiting (allow 5 concurrent async calls)
_async_llm_lock = asyncio.Semaphore(5)


async def call_llm_async(messages: list) -> str:
    llm = _get_llm()
    for attempt in range(2):
        try:
            async with _async_llm_lock:
                result = await llm.ainvoke(messages)
                record_cost(result)
                return result.content
        except Exception as e:
            if attempt == 1:
                raise
            await asyncio.sleep(0.5 * (2 ** attempt))


@retry(max_attempts=2, backoff_base=0.5)
def call_llm_with_tools(messages: list, tools: list):
    """调用 LLM 并绑定工具，返回完整 response（含 tool_calls）"""
    llm = _get_llm()
    with _llm_semaphore:
        llm_with_tools = llm.bind_tools(tools)
        response = llm_with_tools.invoke(messages)
        record_cost(response)
        return response


async def call_llm_with_tools_async(messages: list, tools: list):
    """异步版本：调用 LLM 并绑定工具，返回完整 response（含 tool_calls）"""
    llm = _get_llm()
    for attempt in range(2):
        try:
            async with _async_llm_lock:
                llm_with_tools = llm.bind_tools(tools)
                result = await llm_with_tools.ainvoke(messages)
                record_cost(result)
                return result
        except Exception as e:
            if attempt == 1:
                raise
            await asyncio.sleep(0.5 * (2 ** attempt))
