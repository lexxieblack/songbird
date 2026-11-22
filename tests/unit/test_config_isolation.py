import os
from pathlib import Path

from tests.support.config import AMBIENT_PREFIXES

from songbird.config import Settings


def test_ambient_environment_is_cleared() -> None:
    leaked = [key for key in os.environ if key.startswith(AMBIENT_PREFIXES)]
    assert leaked == []


def test_config_toml_is_not_visible() -> None:
    assert Path("config.toml").exists() is False


def test_settings_use_class_defaults(settings: Settings) -> None:
    assert settings.log_level == "INFO"
    assert settings.llm.model == "gemini-2.5-flash"
    assert settings.llm.system_prompt_path == "prompts/default.xml"


def test_settings_use_fake_credentials(settings: Settings) -> None:
    assert settings.llm.api_key == "test-llm-key"
    assert settings.wolfram.api_key == "test-wolfram-key"
