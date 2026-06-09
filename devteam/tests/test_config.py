"""Tests for the DevTeam configuration module (TDD RED phase)."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Test: Module imports
# ---------------------------------------------------------------------------

class TestConfigImports:
    """The config module must expose Settings and a ready-made settings instance."""

    def test_import_settings_class(self):
        from devteam.config import Settings
        assert Settings is not None

    def test_import_settings_instance(self):
        from devteam.config import settings
        assert settings is not None


# ---------------------------------------------------------------------------
# Test: DeepSeek API defaults
# ---------------------------------------------------------------------------

class TestDeepSeekDefaults:
    """DeepSeek API fields must have sensible defaults."""

    def test_default_api_key_is_empty(self):
        from devteam.config import Settings
        s = Settings()
        assert s.deepseek_api_key == ""

    def test_default_base_url(self):
        from devteam.config import Settings
        s = Settings()
        assert s.deepseek_base_url == "https://api.deepseek.com"

    def test_default_model(self):
        from devteam.config import Settings
        s = Settings()
        assert s.deepseek_model == "deepseek-chat"


# ---------------------------------------------------------------------------
# Test: DeepSeek API override via constructor
# ---------------------------------------------------------------------------

class TestDeepSeekOverride:
    """Values can be overridden via constructor kwargs."""

    def test_override_api_key(self):
        from devteam.config import Settings
        s = Settings(deepseek_api_key="sk-test-123")
        assert s.deepseek_api_key == "sk-test-123"

    def test_override_base_url(self):
        from devteam.config import Settings
        s = Settings(deepseek_base_url="https://custom.api.com")
        assert s.deepseek_base_url == "https://custom.api.com"

    def test_override_model(self):
        from devteam.config import Settings
        s = Settings(deepseek_model="deepseek-reasoner")
        assert s.deepseek_model == "deepseek-reasoner"


# ---------------------------------------------------------------------------
# Test: DeepSeek API override via env vars
# ---------------------------------------------------------------------------

class TestDeepSeekEnvOverride:
    """Values can be overridden via DEVTEAM_ prefixed env vars."""

    def test_env_api_key(self):
        with patch.dict(os.environ, {"DEVTEAM_DEEPSEEK_API_KEY": "sk-env-key"}):
            from devteam.config import Settings
            s = Settings()
            assert s.deepseek_api_key == "sk-env-key"

    def test_env_base_url(self):
        with patch.dict(os.environ, {"DEVTEAM_DEEPSEEK_BASE_URL": "https://env.api.com"}):
            from devteam.config import Settings
            s = Settings()
            assert s.deepseek_base_url == "https://env.api.com"

    def test_env_model(self):
        with patch.dict(os.environ, {"DEVTEAM_DEEPSEEK_MODEL": "env-model"}):
            from devteam.config import Settings
            s = Settings()
            assert s.deepseek_model == "env-model"


# ---------------------------------------------------------------------------
# Test: Discussion config defaults
# ---------------------------------------------------------------------------

class TestDiscussionDefaults:
    """Each agent's discussion config must have sensible defaults."""

    def test_discussion_enabled_default(self):
        from devteam.config import Settings
        s = Settings()
        assert s.discussion_enabled is False  # 默认关闭（mini模式）

    def test_discussion_max_rounds_default(self):
        from devteam.config import Settings
        s = Settings()
        assert s.discussion_max_rounds == 1

    def test_discussion_mode_default(self):
        from devteam.config import Settings
        s = Settings()
        assert s.discussion_mode == "full"


# ---------------------------------------------------------------------------
# Test: Discussion config override
# ---------------------------------------------------------------------------

class TestDiscussionOverride:
    """Discussion config can be overridden."""

    def test_override_enabled(self):
        from devteam.config import Settings
        s = Settings(discussion_enabled=False)
        assert s.discussion_enabled is False

    def test_override_max_rounds(self):
        from devteam.config import Settings
        s = Settings(discussion_max_rounds=5)
        assert s.discussion_max_rounds == 5

    def test_override_mode(self):
        from devteam.config import Settings
        s = Settings(discussion_mode="free")
        assert s.discussion_mode == "free"


# ---------------------------------------------------------------------------
# Test: Discussion prompts per agent
# ---------------------------------------------------------------------------

class TestDiscussionPrompts:
    """Per-agent discussion prompts must be configurable."""

    def test_default_prompts_is_dict(self):
        from devteam.config import Settings
        s = Settings()
        assert isinstance(s.discussion_prompts, dict)

    def test_default_prompts_has_architect(self):
        from devteam.config import Settings
        s = Settings()
        assert "architect" in s.discussion_prompts

    def test_default_prompts_has_developer(self):
        from devteam.config import Settings
        s = Settings()
        assert "developer" in s.discussion_prompts

    def test_default_prompts_has_reviewer(self):
        from devteam.config import Settings
        s = Settings()
        assert "reviewer" in s.discussion_prompts

    def test_override_prompts(self):
        from devteam.config import Settings
        custom = {"architect": "custom prompt", "developer": "dev prompt"}
        s = Settings(discussion_prompts=custom)
        assert s.discussion_prompts == custom


# ---------------------------------------------------------------------------
# Test: Project directory configuration
# ---------------------------------------------------------------------------

class TestProjectDir:
    """Project directory must be configurable and default to a sensible path."""

    def test_default_project_dir(self):
        from devteam.config import Settings
        s = Settings()
        # Should default to a 'projects' directory next to this package
        assert "projects" in s.project_dir

    def test_override_project_dir(self):
        from devteam.config import Settings
        s = Settings(project_dir="/tmp/my_project")
        assert s.project_dir == "/tmp/my_project"

    def test_project_dir_is_string(self):
        from devteam.config import Settings
        s = Settings()
        assert isinstance(s.project_dir, str)


# ---------------------------------------------------------------------------
# Test: Max iterations configuration
# ---------------------------------------------------------------------------

class TestMaxIterations:
    """Max iterations defaults to 3."""

    def test_default_max_iterations(self):
        from devteam.config import Settings
        s = Settings()
        assert s.max_iterations == 3

    def test_override_max_iterations(self):
        from devteam.config import Settings
        s = Settings(max_iterations=10)
        assert s.max_iterations == 10

    def test_max_iterations_is_int(self):
        from devteam.config import Settings
        s = Settings()
        assert isinstance(s.max_iterations, int)


# ---------------------------------------------------------------------------
# Test: Pydantic BaseSettings behavior
# ---------------------------------------------------------------------------

class TestBaseSettingsBehavior:
    """Config must behave as a proper pydantic-settings model."""

    def test_is_pydantic_base_settings(self):
        from pydantic_settings import BaseSettings
        from devteam.config import Settings
        assert issubclass(Settings, BaseSettings)

    def test_model_dump_returns_dict(self):
        from devteam.config import Settings
        s = Settings()
        d = s.model_dump()
        assert isinstance(d, dict)

    def test_model_dump_contains_deepseek_keys(self):
        from devteam.config import Settings
        s = Settings()
        d = s.model_dump()
        assert "deepseek_api_key" in d
        assert "deepseek_base_url" in d
        assert "deepseek_model" in d

    def test_model_dump_contains_max_iterations(self):
        from devteam.config import Settings
        s = Settings()
        d = s.model_dump()
        assert "max_iterations" in d

    def test_model_dump_contains_project_dir(self):
        from devteam.config import Settings
        s = Settings()
        d = s.model_dump()
        assert "project_dir" in d

    def test_env_prefix_is_devteam(self):
        from devteam.config import Settings
        s = Settings()
        # model_config should specify env_prefix
        assert s.model_config.get("env_prefix") == "DEVTEAM_"
