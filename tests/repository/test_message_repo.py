import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
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
