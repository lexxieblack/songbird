import os
from pathlib import Path
from typing import Any

import pytest

from songbird.config import Settings

# Any variable with one of these prefixes in the developer's shell leaks into Settings().
AMBIENT_PREFIXES = ("BOT__", "DB__", "LLM__", "WOLFRAM__", "DISCORD_TOKEN", "LINKS", "LOG_LEVEL")


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(AMBIENT_PREFIXES):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def settings() -> Settings:
    # The dict lets mypy pass the nested payloads BaseSettings accepts; the models build them.
    values: dict[str, Any] = {
        "_env_file": None,
        "DISCORD_TOKEN": "test-token",
        "bot": {},
        "blackwall": {},
        "links": {},
        "db": {"url": "postgresql+psycopg://test:test@localhost:5432/test"},
        "llm": {"api_key": "test-llm-key"},
        "wolfram": {"api_key": "test-wolfram-key"},
    }
    return Settings(**values)
