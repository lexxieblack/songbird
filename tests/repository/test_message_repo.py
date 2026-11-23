import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.repositories.chat.message import MessageRepository

pytestmark = pytest.mark.db


async def test_create_and_read_round_trip(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    created = await repo.create_message(42, MessageRole.USER, "hello")
    await session.commit()

    assert created.content == "hello"
    assert [m.content for m in await repo.get_newest_messages(42)] == ["hello"]


async def test_delete_messages(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    await repo.create_message(42, MessageRole.USER, "one")
    await repo.create_message(42, MessageRole.MODEL, "two")
    await session.commit()

    assert await repo.delete_messages(42) == 2
    assert await repo.get_newest_messages(42) == []


async def test_user_stats(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    await repo.create_message(42, MessageRole.USER, "hello")
    await session.commit()

    assert (await repo.get_user_stats(42)).message_count == 1


async def test_create_returns_db_defaults(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    created = await repo.create_message(42, MessageRole.MODEL, "hi")
    await session.commit()

    assert isinstance(created.id, UUID)
    assert created.role is MessageRole.MODEL
    assert created.created_at.tzinfo is not None


async def test_newest_messages_orders_desc_and_limits(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    for content in ("first", "second", "third"):
        await repo.create_message(42, MessageRole.USER, content)
        await session.commit()

    newest = await repo.get_newest_messages(42, limit=2)

    assert [m.content for m in newest] == ["third", "second"]


async def test_get_all_messages_ascending_with_limit(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    for content in ("first", "second", "third"):
        await repo.create_message(42, MessageRole.USER, content)
        await session.commit()

    assert [m.content for m in await repo.get_all_messages(42)] == ["first", "second", "third"]
    assert [m.content for m in await repo.get_all_messages(42, limit=2)] == ["first", "second"]


async def test_repositories_isolate_users(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    await repo.create_message(1, MessageRole.USER, "mine")
    await repo.create_message(2, MessageRole.USER, "theirs")
    await session.commit()

    assert [m.content for m in await repo.get_all_messages(1)] == ["mine"]
    assert await repo.delete_messages(1) == 1
    await session.commit()
    assert [m.content for m in await repo.get_all_messages(2)] == ["theirs"]


async def test_delete_last_message_removes_only_newest(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    for content in ("first", "second"):
        await repo.create_message(42, MessageRole.USER, content)
        await session.commit()

    await repo.delete_last_message(42)
    await session.commit()

    assert [m.content for m in await repo.get_all_messages(42)] == ["first"]


async def test_delete_last_message_is_noop_when_empty(session: AsyncSession) -> None:
    repo = MessageRepository(session)

    await repo.delete_last_message(42)

    assert await repo.get_all_messages(42) == []


async def test_tied_timestamps_are_ordered_by_id(session: AsyncSession) -> None:
    # One exchange is inserted in a single transaction, so both rows share CURRENT_TIMESTAMP.
    repo = MessageRepository(session)
    await repo.create_message(42, MessageRole.USER, "question")
    await repo.create_message(42, MessageRole.MODEL, "answer")
    await session.commit()

    assert [m.content for m in await repo.get_newest_messages(42)] == ["answer", "question"]
    assert [m.content for m in await repo.get_all_messages(42)] == ["question", "answer"]


async def test_delete_last_message_with_tied_timestamps_deletes_the_reply(session: AsyncSession) -> None:
    repo = MessageRepository(session)
    await repo.create_message(42, MessageRole.USER, "question")
    await repo.create_message(42, MessageRole.MODEL, "answer")
    await session.commit()

    await repo.delete_last_message(42)
    await session.commit()

    assert [m.content for m in await repo.get_all_messages(42)] == ["question"]


async def test_create_message_translates_integrity_error(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_id = uuid.uuid4()
    monkeypatch.setattr("songbird.repositories.chat.message.make_id", lambda: fixed_id)
    repo = MessageRepository(session)
    await repo.create_message(42, MessageRole.USER, "hello")
    await session.commit()

    with pytest.raises(MessageAlreadyExistsError) as exc_info:
        await repo.create_message(42, MessageRole.USER, "duplicate")
    await session.rollback()

    assert str(exc_info.value) == "Message already exists"
    assert exc_info.value.data == {"user_id": 42}
    assert [m.content for m in await repo.get_all_messages(42)] == ["hello"]
