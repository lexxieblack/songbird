# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.config import Settings
from songbird.models.feedback.exceptions import NotForumChannel, ThreadNotFoundError
from songbird.repositories.feedback.thread import ThreadRepository
from songbird.services.feedback import FeedbackService
from tests.support.discord import make_channel

pytestmark = pytest.mark.db


def _forum() -> Any:
    channel = MagicMock(spec=discord.ForumChannel)
    channel.create_thread = AsyncMock(return_value=SimpleNamespace(id=9001))
    return channel


def _thread() -> Any:
    thread = MagicMock(spec=discord.Thread)
    thread.id = 9001
    thread.send = AsyncMock()
    return thread


def _service(bot: Any, session: AsyncSession, settings: Settings) -> FeedbackService:
    return FeedbackService(bot=bot, thread_repo=ThreadRepository(session), settings=settings)


async def test_disabled_feedback_channel_is_a_noop(fake_bot: Any, session: AsyncSession, settings: Settings) -> None:
    settings.bot.feedback_channel_id = None

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is False

    with pytest.raises(ThreadNotFoundError):
        await ThreadRepository(session).get_thread(1)


async def test_existing_thread_receives_message(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    thread = _thread()
    repo = ThreadRepository(session)
    await repo.create_thread(1, 9001)
    monkeypatch.setattr(fake_bot, "get_channel", lambda channel_id: thread if channel_id == 9001 else None)

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is True

    assert thread.send.await_args is not None
    assert thread.send.await_args.args == ("hello",)
    assert thread.send.await_args.kwargs["allowed_mentions"].everyone is False


async def test_thread_send_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    thread = _thread()
    thread.send.side_effect = discord.Forbidden(cast(Any, SimpleNamespace(status=403, reason="Forbidden")), "no access")
    await ThreadRepository(session).create_thread(1, 9001)
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: thread)

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is False


async def test_missing_thread_is_created_and_used(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    settings.bot.feedback_channel_id = 500
    forum, thread = _forum(), _thread()
    channels = {500: forum, 9001: thread}
    monkeypatch.setattr(fake_bot, "get_channel", lambda channel_id: channels.get(channel_id))

    await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello")

    forum.create_thread.assert_awaited_once_with(name="Feedback from alice", content="This is feedback from <@1>")
    assert (await ThreadRepository(session).get_thread(1)).thread_id == 9001
    assert thread.send.await_args is not None
    assert thread.send.await_args.args == ("hello",)


async def test_created_thread_missing_from_cache_skips_send(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    settings.bot.feedback_channel_id = 500
    forum = _forum()
    monkeypatch.setattr(fake_bot, "get_channel", lambda channel_id: forum if channel_id == 500 else None)

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is False

    assert (await ThreadRepository(session).get_thread(1)).thread_id == 9001
    assert forum.create_thread.await_count == 1


async def test_missing_forum_channel_raises(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    settings.bot.feedback_channel_id = 500
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: None)

    with pytest.raises(ThreadNotFoundError):
        await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello")


async def test_non_forum_channel_raises(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    settings.bot.feedback_channel_id = 500
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: make_channel())

    with pytest.raises(NotForumChannel):
        await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello")


@pytest.mark.parametrize(
    "error",
    [
        discord.Forbidden(cast(Any, SimpleNamespace(status=403, reason="Forbidden")), "no access"),
        RuntimeError("boom"),
    ],
)
async def test_thread_creation_failure_is_swallowed(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings, error: Exception
) -> None:
    settings.bot.feedback_channel_id = 500
    forum = _forum()
    forum.create_thread.side_effect = error
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: forum)

    await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello")

    with pytest.raises(ThreadNotFoundError):
        await ThreadRepository(session).get_thread(1)


async def test_thread_row_of_wrong_channel_type_is_forgotten(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    await ThreadRepository(session).create_thread(1, 9001)
    channel = make_channel()
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: channel)

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is False

    assert not cast(Any, channel.send).called
    with pytest.raises(ThreadNotFoundError):
        await ThreadRepository(session).get_thread(1)


async def test_deleted_thread_is_recreated(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    settings.bot.feedback_channel_id = 500
    await ThreadRepository(session).create_thread(1, 9001)

    forum = _forum()
    forum.create_thread = AsyncMock(return_value=SimpleNamespace(id=9002))
    new_thread = _thread()
    new_thread.id = 9002
    channels = {500: forum, 9002: new_thread}
    monkeypatch.setattr(fake_bot, "get_channel", lambda channel_id: channels.get(channel_id))

    assert await _service(fake_bot, session, settings).send_feedback(1, "alice", "hello") is True

    assert (await ThreadRepository(session).get_thread(1)).thread_id == 9002
    assert new_thread.send.await_args is not None
    assert new_thread.send.await_args.args == ("hello",)


async def test_unexpected_repository_error_propagates(
    monkeypatch: pytest.MonkeyPatch, fake_bot: Any, session: AsyncSession, settings: Settings
) -> None:
    repo = ThreadRepository(session)

    async def _broken(_user_id: int) -> Any:
        raise RuntimeError("db down")

    monkeypatch.setattr(repo, "get_thread", _broken)

    with pytest.raises(RuntimeError, match="db down"):
        await FeedbackService(bot=fake_bot, thread_repo=repo, settings=settings).send_feedback(1, "alice", "hello")
