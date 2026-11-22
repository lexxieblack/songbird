import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import GuildBanAlreadyExistsError, GuildBanNotFoundError
from songbird.repositories.management.guild_ban import GuildBanRepository

pytestmark = pytest.mark.db


async def test_create_and_get_round_trip(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)
    created = await repo.create_ban(7, reason="spam")
    await session.commit()

    assert created.reason == "spam"
    assert created.created_at.tzinfo is not None
    fetched = await repo.get_ban(7)
    assert fetched.guild_id == 7
    assert fetched.reason == "spam"


async def test_create_without_reason_stores_null(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)
    created = await repo.create_ban(7)
    await session.commit()

    assert created.reason is None
    assert (await repo.get_ban(7)).reason is None


async def test_get_missing_raises_not_found(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)

    with pytest.raises(GuildBanNotFoundError) as exc_info:
        await repo.get_ban(404)

    assert str(exc_info.value) == "Guild ban not found"
    assert exc_info.value.data == {"guild_id": 404}


async def test_create_duplicate_translates_integrity_error(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)
    await repo.create_ban(7, reason="first")
    await session.commit()

    with pytest.raises(GuildBanAlreadyExistsError) as exc_info:
        await repo.create_ban(7, reason="second")
    await session.rollback()

    assert str(exc_info.value) == "Guild ban already exists"
    assert exc_info.value.data == {"guild_id": 7}
    assert (await repo.get_ban(7)).reason == "first"


async def test_is_banned(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)

    assert await repo.is_banned(7) is False
    await repo.create_ban(7)
    await session.commit()
    assert await repo.is_banned(7) is True


async def test_delete_ban(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)
    await repo.create_ban(7)
    await session.commit()

    await repo.delete_ban(7)
    await session.commit()

    assert await repo.is_banned(7) is False
    with pytest.raises(GuildBanNotFoundError):
        await repo.delete_ban(7)


async def test_list_bans_orders_newest_first(session: AsyncSession) -> None:
    repo = GuildBanRepository(session)
    await repo.create_ban(1)
    await session.commit()
    await repo.create_ban(2)
    await session.commit()

    assert [ban.guild_id for ban in await repo.list_bans()] == [2, 1]
