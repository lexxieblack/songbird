from pathlib import Path

import pytest

from songbird.utils.prompts import DEFAULT_SYSTEM_PROMPT, SafeDict, build_user_context, get_system_prompt, load_prompt


def test_safe_dict_keeps_unknown_placeholders() -> None:
    assert "{unknown}".format_map(SafeDict()) == "{unknown}"


def test_safe_dict_formats_known_keys() -> None:
    assert "{name} {missing}".format_map(SafeDict({"name": "Songbird"})) == "Songbird {missing}"


@pytest.mark.parametrize(
    ("guild_name", "channel_name", "expected"),
    [
        (None, None, "User: alice (ID: 1)\nContext: Direct message (DM)"),
        ("Night City", None, "User: alice (ID: 1)\nServer: Night City\nContext: Guild/server conversation"),
        (
            "Night City",
            "general",
            "User: alice (ID: 1)\nServer: Night City\nServer channel: general\nContext: Guild/server conversation",
        ),
        (None, "general", "User: alice (ID: 1)\nContext: Direct message (DM)"),
    ],
)
def test_build_user_context(guild_name: str | None, channel_name: str | None, expected: str) -> None:
    assert build_user_context(1, "alice", guild_name, channel_name) == expected


def test_get_system_prompt_without_a_path_returns_the_default() -> None:
    assert get_system_prompt() == DEFAULT_SYSTEM_PROMPT


def test_get_system_prompt_falls_back_to_the_default_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "default.xml").write_text("Default persona {datetime}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    prompt = get_system_prompt(str(tmp_path / "missing.xml"))

    assert prompt.startswith("Default persona 20")


def test_get_system_prompt_falls_back_to_hard_coded_prompt_when_default_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert get_system_prompt(str(tmp_path / "missing.xml")) == DEFAULT_SYSTEM_PROMPT


def test_get_system_prompt_formats_datetime_and_keeps_unknown_placeholders(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.xml"
    prompt_file.write_text("Now: {datetime}\nKeep {unknown}", encoding="utf-8")

    prompt = get_system_prompt(str(prompt_file))

    assert prompt.startswith("Now: 20")
    assert "(UK local time)" in prompt
    assert "{datetime}" not in prompt
    assert "{unknown}" in prompt


def test_load_prompt_reads_the_file_verbatim(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("line one\nline two\n", encoding="utf-8")

    assert load_prompt(prompt_file) == "line one\nline two\n"


def test_load_prompt_raises_for_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Prompt file not found"):
        load_prompt(tmp_path / "missing.txt")


def test_load_prompt_caches_by_resolved_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("first", encoding="utf-8")

    assert load_prompt("prompt.txt") == "first"

    prompt_file.write_text("second", encoding="utf-8")

    assert load_prompt(prompt_file) == "first"
