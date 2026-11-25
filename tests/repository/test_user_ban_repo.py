import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import UserBanAlreadyExistsError, UserBanNotFoundError
from songbird.repositories.management.user_ban import UserBanRepository

pytestmark = pytest.mark.db


async def test_create_and_list_round_trip(session: AsyncSession) -> None:
    repo = UserBanRepository(session)
    created = await repo.create_ban(7, reason="harassment")
    await session.commit()

    assert created.reason == "harassment"
    assert created.created_at.tzinfo is not None
    [fetched] = await repo.list_bans()
    assert fetched.user_id == 7
    assert fetched.reason == "harassment"


async def test_create_without_reason_stores_null(session: AsyncSession) -> None:
    repo = UserBanRepository(session)
    created = await repo.create_ban(7)
    await session.commit()

    assert created.reason is None
    [fetched] = await repo.list_bans()
    assert fetched.reason is None


async def test_create_duplicate_translates_integrity_error(session: AsyncSession) -> None:
    repo = UserBanRepository(session)
    await repo.create_ban(7, reason="first")
    await session.commit()

    with pytest.raises(UserBanAlreadyExistsError) as exc_info:
        await repo.create_ban(7, reason="second")
    await session.rollback()

    assert str(exc_info.value) == "User ban already exists"
    assert exc_info.value.data == {"user_id": 7}
    [fetched] = await repo.list_bans()
    assert fetched.reason == "first"


async def test_is_banned(session: AsyncSession) -> None:
    repo = UserBanRepository(session)

    assert await repo.is_banned(7) is False
    await repo.create_ban(7)
    await session.commit()
    assert await repo.is_banned(7) is True


async def test_delete_ban(session: AsyncSession) -> None:
    repo = UserBanRepository(session)
    await repo.create_ban(7)
    await session.commit()

    await repo.delete_ban(7)
    await session.commit()

    assert await repo.is_banned(7) is False
    with pytest.raises(UserBanNotFoundError):
        await repo.delete_ban(7)


async def test_list_bans_orders_newest_first(session: AsyncSession) -> None:
    repo = UserBanRepository(session)
    await repo.create_ban(1)
    await session.commit()
    await repo.create_ban(2)
    await session.commit()

    assert [ban.user_id for ban in await repo.list_bans()] == [2, 1]
