import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.exceptions import UserInfoAlreadyExistsError, UserInfoNotFoundError
from songbird.repositories.chat.user_info import UserInfoRepository

pytestmark = pytest.mark.db


async def test_create_and_get_round_trip(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)
    created = await repo.create_user_info(7, "bio")
    await session.commit()

    assert created.user_info == "bio"
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None

    fetched = await repo.get_user_info(7)
    assert fetched.user_id == 7
    assert fetched.user_info == "bio"
    assert fetched.created_at == created.created_at


async def test_get_missing_raises_not_found(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)

    with pytest.raises(UserInfoNotFoundError) as exc_info:
        await repo.get_user_info(404)

    assert str(exc_info.value) == "User info not found"
    assert exc_info.value.data == {"user_id": 404}


async def test_create_duplicate_translates_integrity_error(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)
    await repo.create_user_info(7, "bio")
    await session.commit()

    with pytest.raises(UserInfoAlreadyExistsError) as exc_info:
        await repo.create_user_info(7, "other")
    await session.rollback()

    assert str(exc_info.value) == "User info already exists"
    assert exc_info.value.data == {"user_id": 7}
    assert (await repo.get_user_info(7)).user_info == "bio"


async def test_update_returns_new_value(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)
    await repo.create_user_info(7, "old")
    await session.commit()

    updated = await repo.update_user_info(7, "new")
    await session.commit()

    assert updated.user_info == "new"
    assert (await repo.get_user_info(7)).user_info == "new"


async def test_update_missing_raises_not_found(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)

    with pytest.raises(UserInfoNotFoundError) as exc_info:
        await repo.update_user_info(404, "new")

    assert exc_info.value.data == {"user_id": 404}


async def test_delete_returns_rowcount(session: AsyncSession) -> None:
    repo = UserInfoRepository(session)
    await repo.create_user_info(7, "bio")
    await session.commit()

    assert await repo.delete_user_info(7) == 1
    await session.commit()
    assert await repo.delete_user_info(7) == 0
    assert await repo.delete_user_info(404) == 0
