# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

"""`on_message` chat listener: gating, reply context, and handler failures."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.listeners import chat
from tests.support.discord import make_channel, make_guild, make_member, make_message

pytestmark = pytest.mark.discord

Listener = Callable[..., Awaitable[None]]


@asynccontextmanager
async def _session(_services: object) -> AsyncGenerator[object]:
    yield object()


def _listener(bot: SongbirdBot) -> Listener:
    return cast(Listener, vars(bot)["listeners"][0])


def _install_handler(monkeypatch: pytest.MonkeyPatch, response: str | None = "reply") -> SimpleNamespace:
    handler = SimpleNamespace(chat=AsyncMock(return_value=response))
    monkeypatch.setattr(chat, "get_session", _session)
    monkeypatch.setattr(chat, "create_private_conversation_service", lambda *_, **__: object())
    monkeypatch.setattr(chat, "create_guild_conversation_service", lambda *_, **__: object())
    monkeypatch.setattr(chat, "PrivateChatHandler", lambda *_, **__: handler)
    monkeypatch.setattr(chat, "GuildChatHandler", lambda *_, **__: handler)
    return handler


def _management(
    bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch, *, user_banned: bool = False, guild_banned: bool = False
) -> None:
    monkeypatch.setattr(
        bot.services,
        "management",
        SimpleNamespace(
            check_user_banned=AsyncMock(return_value=user_banned),
            check_guild_banned=AsyncMock(return_value=guild_banned),
        ),
    )


def _dm_message(content: str = "hello") -> tuple[discord.Message, AsyncMock]:
    send = AsyncMock()
    channel = MagicMock(spec=discord.DMChannel, send=send, trigger_typing=AsyncMock())
    author: Any = make_member(id=7, bot=False)
    author.name = "bob"
    author.display_name = "Bob"
    message = make_message(content=content, channel=channel, author=author)
    message.guild = None
    message.reference = None
    return message, send


def _guild_message(content: str = "hello", *, mentions: list[Any] | None = None) -> tuple[discord.Message, Any, AsyncMock]:
    send = AsyncMock()
    channel = make_channel(send=send, trigger_typing=AsyncMock())
    channel.name = "general"
    guild: Any = make_guild(leave=AsyncMock())
    guild.id = 3
    guild.name = "Test Guild"
    author: Any = make_member(id=7, bot=False)
    author.name = "bob"
    author.display_name = "Bob"
    message = make_message(content=content, channel=channel, author=author, guild=guild)
    message.mentions = mentions or []
    message.reference = None
    return message, guild, send


async def test_bot_message_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    message, send = _dm_message()
    message.author.bot = True
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_not_awaited()
    send.assert_not_awaited()


async def test_empty_content_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    message, send = _dm_message(content="")
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_not_awaited()
    send.assert_not_awaited()


async def test_dm_from_allowed_user_gets_private_chat(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch, response="a reply")
    _management(fake_bot, monkeypatch)
    message, send = _dm_message("hi there")
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_awaited_once()
    assert handler.chat.await_args is not None
    kwargs = handler.chat.await_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["message"] == "hi there"
    assert kwargs["username"] == "bob"
    assert kwargs["channel_name"] == "DM with bob"

    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args == ("a reply",)


async def test_banned_user_dm_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    _management(fake_bot, monkeypatch, user_banned=True)
    message, send = _dm_message()
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_not_awaited()
    send.assert_not_awaited()


async def test_guild_message_without_mention_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    _management(fake_bot, monkeypatch)
    message, guild, send = _guild_message()
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_not_awaited()
    guild.leave.assert_not_called()
    send.assert_not_awaited()


async def test_guild_message_mentioning_bot_gets_guild_chat(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch, response="a reply")
    _management(fake_bot, monkeypatch)
    message, _, send = _guild_message("hello", mentions=[fake_bot.user])
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    handler.chat.assert_awaited_once()
    assert handler.chat.await_args is not None
    kwargs = handler.chat.await_args.kwargs
    assert kwargs["guild_id"] == 3
    assert kwargs["channel_name"] == "general"
    assert kwargs["guild_name"] == "Test Guild"
    assert send.await_args is not None
    assert send.await_args.args == ("a reply",)


async def test_mention_is_replaced_with_bot_display_name(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    _management(fake_bot, monkeypatch)
    user = fake_bot.user
    assert user is not None
    message, _, _ = _guild_message(f"<@{user.id}> hello", mentions=[user])
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    assert handler.chat.await_args is not None
    assert handler.chat.await_args.kwargs["message"] == "Songbird hello"


async def test_banned_guild_is_left_on_mention(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    _management(fake_bot, monkeypatch, guild_banned=True)
    message, guild, send = _guild_message("hello", mentions=[fake_bot.user])
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    guild.leave.assert_awaited_once()
    handler.chat.assert_not_awaited()
    send.assert_not_awaited()


async def test_no_response_sends_fallback(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_handler(monkeypatch, response=None)
    _management(fake_bot, monkeypatch)
    message, send = _dm_message()
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args == ("My neural pathways got a bit scrambled.",)
    assert isinstance(send.await_args.kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_handler_exception_falls_back_to_error_message(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    handler.chat.side_effect = RuntimeError("llm down")
    _management(fake_bot, monkeypatch)
    message, send = _dm_message()
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    send.assert_awaited_once()
    assert send.await_args is not None
    assert "scrambled" in send.await_args.args[0]


async def test_guild_handler_exception_falls_back_to_error_message(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    handler = _install_handler(monkeypatch)
    handler.chat.side_effect = RuntimeError("llm down")
    _management(fake_bot, monkeypatch)
    message, _, send = _guild_message("hello", mentions=[fake_bot.user])
    chat.load_chat(fake_bot)

    await _listener(fake_bot)(message)

    send.assert_awaited_once()
    assert send.await_args is not None
    assert "scrambled" in send.await_args.args[0]


@pytest.mark.parametrize("channel_cls", [discord.VoiceChannel, discord.ForumChannel])
async def test_other_channel_types_are_ignored(fake_bot: SongbirdBot, channel_cls: type[discord.abc.GuildChannel]) -> None:
    message = make_message(
        content="hello",
        author=make_member(bot=False),
        channel=MagicMock(spec=channel_cls),
    )

    assert await chat._is_message_relevant(fake_bot, message) is False


def test_reply_context_without_reference_is_unchanged() -> None:
    message = make_message()
    message.reference = None

    assert chat._get_reply_context(message, "hello") == "hello"


def test_reply_context_includes_referenced_message() -> None:
    author: Any = make_member(id=7)
    author.name = "bob"
    author.display_name = "Bob"
    reply_author: Any = make_member(id=8)
    reply_author.name = "alice"
    reply_author.display_name = "Alice"
    referenced = make_message(content="original")
    referenced.author = reply_author

    message = make_message(author=author, reference=SimpleNamespace(resolved=referenced))

    text = chat._get_reply_context(message, "current")

    assert "<message>current</message>" in text
    assert "<reply_message>original</reply_message>" in text
    assert "Message from Bob" in text
    assert "In reply to Alice's message" in text


def test_reply_context_notes_deleted_message() -> None:
    message = make_message(
        author=make_member(),
        reference=SimpleNamespace(resolved=MagicMock(spec=discord.DeletedReferencedMessage)),
    )

    assert chat._get_reply_context(message, "current").endswith("In reply to a deleted message")
