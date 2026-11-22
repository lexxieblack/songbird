# pyright: reportPrivateUsage=false

"""Link fixer listener: URL detection, embed suppression, restore flow, cache."""

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.listeners import link_fixer as link_fixer_module
from songbird.listeners.link_fixer import CACHED_MESSAGES
from songbird.ui.views.link_fixer import RestoreLinkView
from tests.support.discord import make_channel, make_fake_bot, make_member, make_message

pytestmark = pytest.mark.discord

Listener = Callable[..., Awaitable[None]]


def _settings(links: dict[str, Any]) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "DISCORD_TOKEN": "test-token",
        "bot": {},
        "blackwall": {},
        "db": {"url": "postgresql+psycopg://test:test@localhost:5432/test"},
        "llm": {"api_key": "test-llm-key"},
        "wolfram": {"api_key": "test-wolfram-key"},
        "links": links,
    }
    return Settings(**values)


def _fake_extract(url: str) -> SimpleNamespace:
    host = urlparse(url).hostname or ""
    domain, _, suffix = host.rpartition(".")
    domain = domain.rpartition(".")[2]
    return SimpleNamespace(domain=domain, suffix=suffix)


@pytest.fixture(autouse=True)
def _offline_tldextract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(link_fixer_module, "tldextract", SimpleNamespace(extract=_fake_extract))


def _listener(bot: SongbirdBot, index: int) -> Listener:
    return cast(Listener, vars(bot)["listeners"][index])


def _message(
    content: str = "https://example.com/a",
    *,
    channel: Any = None,
    edit: AsyncMock | None = None,
    bot_author: bool = False,
) -> tuple[Any, AsyncMock, AsyncMock]:
    send = AsyncMock(return_value=make_message())
    target = channel if channel is not None else make_channel(send=send)
    author = make_member(bot=bot_author)
    edit_mock = edit or AsyncMock()
    message = make_message(
        id=10,
        content=content,
        author=author,
        channel=target,
        edit=edit_mock,
        attachments=[],
    )
    return message, edit_mock, send


def _response(status: int, reason: str) -> Any:
    return SimpleNamespace(status=status, reason=reason)


def _bot_with_fix(monkeypatch: pytest.MonkeyPatch, *fix_returns: list[str]) -> tuple[SongbirdBot, AsyncMock]:
    bot = make_fake_bot(_settings({"example.com": {"chat": True}}))
    fix = AsyncMock(side_effect=list(fix_returns))
    monkeypatch.setattr(bot.services, "link_fixer", SimpleNamespace(fix=fix))
    link_fixer_module.load_fix(bot)
    return bot, fix


async def test_bot_author_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, fix = _bot_with_fix(monkeypatch, [])
    message, _, send = _message(bot_author=True)

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()
    send.assert_not_awaited()


async def test_empty_content_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, fix = _bot_with_fix(monkeypatch, [])
    message, _, send = _message("")

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.parametrize("channel_cls", [discord.DMChannel, discord.VoiceChannel])
async def test_non_text_channels_are_ignored(monkeypatch: pytest.MonkeyPatch, channel_cls: type[discord.abc.Messageable]) -> None:
    bot, fix = _bot_with_fix(monkeypatch, [])
    message, _, _ = _message(channel=MagicMock(spec=channel_cls))

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()


async def test_unknown_domain_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = make_fake_bot(_settings({}))
    fix = AsyncMock()
    monkeypatch.setattr(bot.services, "link_fixer", SimpleNamespace(fix=fix))
    link_fixer_module.load_fix(bot)
    message, edit, send = _message()

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()
    edit.assert_not_awaited()
    send.assert_not_awaited()


async def test_domain_without_chat_enabled_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = make_fake_bot(_settings({"example.com": {"swap": "fix.example.com"}}))
    fix = AsyncMock()
    monkeypatch.setattr(bot.services, "link_fixer", SimpleNamespace(fix=fix))
    link_fixer_module.load_fix(bot)
    message, _, _ = _message()

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()


async def test_message_without_urls_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, fix = _bot_with_fix(monkeypatch, [])
    message, edit, send = _message("no links here")

    await _listener(bot, 1)(message)

    fix.assert_not_awaited()
    edit.assert_not_awaited()
    send.assert_not_awaited()


async def test_fixable_url_is_replaced_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, fix = _bot_with_fix(monkeypatch, ["https://example.com/fixed"])
    message, edit, send = _message()

    await _listener(bot, 1)(message)

    fix.assert_awaited_once_with("https://example.com/a")
    edit.assert_awaited_once_with(suppress_embeds=True)
    assert message.id in CACHED_MESSAGES

    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args == ("[example.com](https://example.com/fixed)",)
    assert send.await_args.kwargs["reference"] is message
    assert isinstance(send.await_args.kwargs["view"], RestoreLinkView)
    assert isinstance(send.await_args.kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_extra_fixed_urls_are_sent_without_view(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, fix = _bot_with_fix(monkeypatch, ["https://example.com/fixed"], ["https://example.com/also"])
    message, _, send = _message("https://example.com/a https://example.com/b")

    await _listener(bot, 1)(message)

    assert fix.await_count == 2
    assert send.await_count == 2
    second = send.await_args_list[1]
    assert second.args == ("[example.com](https://example.com/also)",)
    assert "view" not in second.kwargs


async def test_empty_fix_result_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, [])
    message, edit, send = _message()

    await _listener(bot, 1)(message)

    edit.assert_not_awaited()
    send.assert_not_awaited()
    assert message.id not in CACHED_MESSAGES


async def test_missing_manage_messages_permission_warns_and_still_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, ["https://example.com/fixed"])
    edit = AsyncMock(side_effect=discord.Forbidden(_response(403, "Forbidden"), "missing"))
    message, _, send = _message(edit=edit)

    await _listener(bot, 1)(message)

    assert send.await_count == 2
    warning = send.await_args_list[0]
    assert "missing permission" in warning.args[0]
    assert warning.kwargs["delete_after"] == 10
    assert warning.kwargs["reference"] is message
    assert send.await_args_list[1].args == ("[example.com](https://example.com/fixed)",)


async def test_embed_suppression_http_error_is_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, ["https://example.com/fixed"])
    edit = AsyncMock(side_effect=discord.HTTPException(_response(500, "Server Error"), "boom"))
    message, _, send = _message(edit=edit)

    await _listener(bot, 1)(message)

    edit.assert_awaited_once_with(suppress_embeds=True)
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args == ("[example.com](https://example.com/fixed)",)


async def test_cached_message_edit_suppresses_embeds_and_forgets_id(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, [])
    after_edit = AsyncMock()
    after = make_message(id=10, edit=after_edit)
    before = make_message(id=10)
    CACHED_MESSAGES.add(10)

    await _listener(bot, 0)(before, after)

    after_edit.assert_awaited_once_with(suppress_embeds=True)
    assert 10 not in CACHED_MESSAGES


async def test_uncached_message_edit_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, [])
    after_edit = AsyncMock()

    await _listener(bot, 0)(make_message(id=99), make_message(id=99, edit=after_edit))

    after_edit.assert_not_awaited()


async def test_cached_message_edit_http_error_is_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    bot, _ = _bot_with_fix(monkeypatch, [])
    after_edit = AsyncMock(side_effect=discord.HTTPException(_response(500, "Server Error"), "boom"))
    CACHED_MESSAGES.add(10)

    await _listener(bot, 0)(make_message(id=10), make_message(id=10, edit=after_edit))

    after_edit.assert_awaited_once()
    assert 10 not in CACHED_MESSAGES


def test_unload_clears_cached_messages() -> None:
    CACHED_MESSAGES.add(1)

    link_fixer_module.unload_fix()

    assert not CACHED_MESSAGES


def test_get_urls_finds_http_and_https_links() -> None:
    text = "look at http://a.example/x and https://b.example/y?q=1"

    assert link_fixer_module._get_urls(text) == ["http://a.example/x", "https://b.example/y?q=1"]


def test_domain_setting_requires_chat_enabled() -> None:
    links = _settings({"example.com": {"chat": True}, "other.com": {"chat": False}}).links

    assert link_fixer_module._check_domain_setting("https://example.com/a", links) is True
    assert link_fixer_module._check_domain_setting("https://other.com/a", links) is False
    assert link_fixer_module._check_domain_setting("https://unknown.com/a", links) is False
