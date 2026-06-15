"""Blueprint project configuration.

Uses pydantic-settings so every field can be overridden via
BLUEPRINT_* environment variables or a .env file.
"""

from pathlib import Path
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings


_DEFAULT_PROJECTS_DIR = str(Path(__file__).resolve().parent / "projects")

_DEFAULT_DISCUSSION_PROMPTS: Dict[str, str] = {
    "pm": (
        "你是资深产品经理。分析用户需求，拆解为用户故事和功能清单。"
        "输出必须包含明确的验收标准，不允许模糊表述。"
    ),
    "pm_critic": (
        "你是技术负责人。从可行性、完整性、边界条件角度审查需求分析。"
        "检查是否有遗漏、歧义、不可测试的验收标准。"
    ),
    "architect": (
        "你是系统架构师。设计技术方案，定义模块、接口、数据模型。"
        "不要过度设计，MVP阶段够用就行。"
    ),
    "architect_critic": (
        "你是架构审查专家。关注扩展性、性能瓶颈、安全风险。"
        "检查接口是否清晰、数据模型是否完整。"
    ),
    "developer": (
        "你是高级程序员。按照架构设计实现代码。"
        "必须有错误处理、输入校验、清晰命名。"
    ),
    "developer_critic": (
        "你是代码审查专家。只标记critical级别问题：安全漏洞、逻辑错误、崩溃风险。"
        "不要纠结代码风格。"
    ),
    "reviewer": (
        "你是代码审查专家。按维度检查：placeholder扫描、一致性、边界、风格。"
        "每个问题必须指出具体文件和行号。"
    ),
}


class Settings(BaseSettings):
    """Central configuration for the Blueprint multi-agent system."""

    # -- LLM API (OpenAI兼容接口) --------------------------------------------
    llm_api_key: str = ""  # 必须通过环境变量或.env设置
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"

    # -- DeepSeek API (向后兼容) ---------------------------------------------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # -- Agent Execution Mode -------------------------------------------------
    # "max" = Proposer-Critic enabled (higher quality, slower)
    # "mini" = Proposer-Critic disabled (faster, lower quality)
    agent_mode: str = "mini"  # "max" | "mini"

    # -- Discussion (only when agent_mode="max") ------------------------------
    discussion_enabled: bool = False  # Controlled by agent_mode
    discussion_max_rounds: int = 1
    discussion_mode: str = "full"  # "full" | "post_review"
    discussion_prompts: Dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_DISCUSSION_PROMPTS),
    )

    # -- UI Settings ----------------------------------------------------------
    show_discussion: bool = False  # Show discussion panel in frontend (only when agent_mode="max")

    # -- Auth ------------------------------------------------------------------
    auth_enabled: bool = False
    auth_keys: str = "{}"  # JSON格式 {"user_id": "api_key"}

    # -- Project directory ---------------------------------------------------
    project_dir: str = _DEFAULT_PROJECTS_DIR

    # -- Feature Toggles ------------------------------------------------------
    tool_progress_enabled: bool = True
    cost_tracking_enabled: bool = True
    auto_fix_enabled: bool = True

    # -- Max iterations ------------------------------------------------------
    max_iterations: int = 3

    # -- JWT ------------------------------------------------------------------
    jwt_secret: str = ""  # 未设置时随机生成（重启后token失效）

    # -- pydantic-settings config --------------------------------------------
    model_config = {
        "env_prefix": "BLUEPRINT_",
        "env_file": str(Path(__file__).resolve().parent / ".env"),
        "env_file_encoding": "utf-8",
    }


# Module-level singleton -- importable as `from blueprint.config import settings`
settings = Settings()

# Warn if API key is not set
if not settings.llm_api_key:
    import warnings
    warnings.warn(
        "BLUEPRINT_LLM_API_KEY 未设置，LLM调用将失败。"
        "请在环境变量或 .env 文件中设置 BLUEPRINT_LLM_API_KEY。",
        stacklevel=2,
    )
