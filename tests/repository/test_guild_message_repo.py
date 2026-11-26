import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.repositories.chat.message import GuildMessageRepository

pytestmark = pytest.mark.db


async def test_create_and_read_round_trip(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)
    created = await repo.create_message(7, MessageRole.USER, "hello")
    await session.commit()

    assert isinstance(created.id, UUID)
    assert created.guild_id == 7
    assert created.role is MessageRole.USER
    assert created.created_at.tzinfo is not None
    assert [m.content for m in await repo.get_newest_messages(7)] == ["hello"]


async def test_newest_messages_orders_desc_and_limits(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)
    for content in ("first", "second", "third"):
        await repo.create_message(7, MessageRole.MODEL, content)
        await session.commit()

    newest = await repo.get_newest_messages(7, limit=2)

    assert [m.content for m in newest] == ["third", "second"]


async def test_repositories_isolate_guilds(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)
    await repo.create_message(1, MessageRole.USER, "mine")
    await repo.create_message(2, MessageRole.USER, "theirs")
    await session.commit()

    assert [m.content for m in await repo.get_newest_messages(1)] == ["mine"]
    assert await repo.delete_messages(1) == 1
    await session.commit()
    assert [m.content for m in await repo.get_newest_messages(2)] == ["theirs"]


async def test_delete_last_message_removes_only_newest(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)
    for content in ("first", "second"):
        await repo.create_message(7, MessageRole.USER, content)
        await session.commit()

    await repo.delete_last_message(7)
    await session.commit()

    assert [m.content for m in await repo.get_newest_messages(7)] == ["first"]


async def test_delete_last_message_is_noop_when_empty(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)

    await repo.delete_last_message(7)

    assert await repo.get_newest_messages(7) == []


async def test_tied_timestamps_are_ordered_by_id(session: AsyncSession) -> None:
    repo = GuildMessageRepository(session)
    await repo.create_message(7, MessageRole.USER, "question")
    await repo.create_message(7, MessageRole.MODEL, "answer")
    await session.commit()

    assert [m.content for m in await repo.get_newest_messages(7)] == ["answer", "question"]

    await repo.delete_last_message(7)
    await session.commit()

    assert [m.content for m in await repo.get_newest_messages(7)] == ["question"]


async def test_create_message_translates_integrity_error(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_id = uuid.uuid4()
    monkeypatch.setattr("songbird.repositories.chat.message.make_id", lambda: fixed_id)
    repo = GuildMessageRepository(session)
    await repo.create_message(7, MessageRole.USER, "hello")
    await session.commit()

    with pytest.raises(MessageAlreadyExistsError) as exc_info:
        await repo.create_message(7, MessageRole.USER, "duplicate")
    await session.rollback()

    assert str(exc_info.value) == "Message already exists"
    assert exc_info.value.data == {"guild_id": 7}
