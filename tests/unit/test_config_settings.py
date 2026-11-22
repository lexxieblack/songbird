"""Settings defaults, validation and source precedence (toml > init > env)."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from songbird.config import Settings, load_config

BASE: dict[str, object] = {
    "DISCORD_TOKEN": "init-token",
    "bot": {},
    "blackwall": {},
    "db": {"url": "postgresql+psycopg://init"},
    "llm": {"api_key": "init-llm"},
    "wolfram": {"api_key": "init-wolfram"},
    "links": {},
}


def _build(**overrides: object) -> Settings:
    values: dict[str, Any] = {"_env_file": None, **overrides}
    return Settings(**values)


def _settings(**overrides: object) -> Settings:
    return _build(**{**BASE, **overrides})


def test_defaults() -> None:
    settings = _settings()

    assert settings.log_level == "INFO"
    assert settings.bot.command_prefix == "/"
    assert settings.bot.status == "online"
    assert settings.bot.activity == "Hello World"
    assert settings.bot.owner_id is None
    assert settings.bot.debug_guild_id is None
    assert settings.llm.model == "gemini-2.5-flash"
    assert settings.llm.message_count == 30
    assert settings.llm.retry.max_attempts == 5
    assert settings.llm.retry.initial_delay == 1.0
    assert settings.llm.retry.max_delay == 60.0
    assert settings.llm.export_cooldown_seconds == 7200
    assert settings.blackwall.image_url is None
    assert len(settings.links.root) == 0


def test_required_fields_are_enforced() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _build(bot={}, blackwall={}, db={"url": "x"}, llm={"api_key": "k"}, wolfram={"api_key": "w"}, links={})

    missing = {error["loc"] for error in excinfo.value.errors()}
    assert ("DISCORD_TOKEN",) in missing


def test_nested_env_vars_use_double_underscore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env-token")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("BOT__OWNER_ID", "42")
    monkeypatch.setenv("BOT__ACTIVITY", "env-activity")
    monkeypatch.setenv("DB__URL", "postgresql+psycopg://env")
    monkeypatch.setenv("LLM__API_KEY", "env-llm")
    monkeypatch.setenv("LLM__RETRY__MAX_ATTEMPTS", "9")
    monkeypatch.setenv("WOLFRAM__API_KEY", "env-wolfram")

    settings = _build(blackwall={}, links={})

    assert settings.discord_token == "env-token"
    assert settings.log_level == "DEBUG"
    assert settings.bot.owner_id == 42
    assert settings.bot.activity == "env-activity"
    assert settings.db.url == "postgresql+psycopg://env"
    assert settings.llm.api_key == "env-llm"
    assert settings.llm.retry.max_attempts == 9
    assert settings.wolfram.api_key == "env-wolfram"


def test_nested_debug_guild_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT__DEBUG_GUILD_ID", "123")

    assert _build(**BASE).bot.debug_guild_id == 123


def test_init_kwargs_beat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM__API_KEY", "env-llm")
    monkeypatch.setenv("BOT__OWNER_ID", "1")

    settings = _settings(llm={"api_key": "init-wins"}, bot={"owner_id": 2})

    assert settings.llm.api_key == "init-wins"
    assert settings.bot.owner_id == 2


def test_invalid_env_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT__OWNER_ID", "not-a-number")

    with pytest.raises(ValidationError):
        _build(**BASE)


def test_toml_beats_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        "\n".join(
            [
                'DISCORD_TOKEN = "toml-token"',
                'log_level = "WARNING"',
                "[bot]",
                "owner_id = 7",
                "[blackwall]",
                "[db]",
                'url = "postgresql+psycopg://toml"',
                "[llm]",
                'api_key = "toml-llm"',
                "[wolfram]",
                'api_key = "toml-wolfram"',
                "[links]",
            ]
        )
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT__OWNER_ID", "99")
    monkeypatch.setenv("LLM__API_KEY", "env-llm")

    settings = _build()

    assert settings.discord_token == "toml-token"
    assert settings.log_level == "WARNING"
    assert settings.bot.owner_id == 7
    assert settings.llm.api_key == "toml-llm"


def test_load_config_reads_config_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.toml").write_text(
        "\n".join(
            [
                'DISCORD_TOKEN = "toml-token"',
                "[bot]",
                "owner_id = 8",
                "[blackwall]",
                "[db]",
                'url = "postgresql+psycopg://toml"',
                "[llm]",
                'api_key = "toml-llm"',
                "[wolfram]",
                'api_key = "toml-wolfram"',
                "[links]",
            ]
        )
    )
    monkeypatch.chdir(tmp_path)

    settings = load_config()

    assert settings.bot.owner_id == 8
    assert settings.llm.api_key == "toml-llm"


def test_links_root_model_parses_domain_overrides() -> None:
    settings = _settings(
        links={
            "example.com": {
                "swap": "fxtwitter.com",
                "follow": True,
                "clean": False,
                "clean_exceptions": ["id"],
                "chat": True,
                "pagination": {"format": "{url}/page/{page}", "per_page": 5, "api": "https://api.example"},
            }
        }
    )

    mapping = settings.links.root["example.com"]
    assert mapping.swap == "fxtwitter.com"
    assert mapping.follow is True
    assert mapping.clean is False
    assert mapping.clean_exceptions == ["id"]
    assert mapping.chat is True
    assert mapping.pagination is not None
    assert mapping.pagination.per_page == 5
    assert mapping.pagination.api == "https://api.example"


def test_links_pagination_defaults() -> None:
    settings = _settings(links={"*": {}})

    mapping = settings.links.root["*"]
    assert mapping.pagination is None
    assert mapping.swap is None


def test_privacy_and_terms_urls() -> None:
    settings = _settings(bot={"source_code_url": "https://github.com/example/songbird"})

    assert settings.bot.privacy_policy_url == "https://github.com/example/songbird/blob/main/PRIVACY.md"
    assert settings.bot.terms_of_service_url == "https://github.com/example/songbird/blob/main/TERMS.md"


def test_privacy_and_terms_urls_absent_without_source() -> None:
    settings = _settings()

    assert settings.bot.privacy_policy_url is None
    assert settings.bot.terms_of_service_url is None
