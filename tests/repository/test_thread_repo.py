import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.feedback.exceptions import ThreadAlreadyExistsError, ThreadNotFoundError
from songbird.repositories.feedback.thread import ThreadRepository

pytestmark = pytest.mark.db


async def test_create_and_get_round_trip(session: AsyncSession) -> None:
    repo = ThreadRepository(session)
    created = await repo.create_thread(7, 70)
    await session.commit()

    assert created.thread_id == 70
    assert created.created_at.tzinfo is not None
    assert (await repo.get_thread(7)).thread_id == 70


async def test_get_missing_raises_not_found(session: AsyncSession) -> None:
    repo = ThreadRepository(session)

    with pytest.raises(ThreadNotFoundError) as exc_info:
        await repo.get_thread(404)

    assert str(exc_info.value) == "Thread not found"
    assert exc_info.value.data == {"user_id": 404}


async def test_create_duplicate_user_translates_integrity_error(session: AsyncSession) -> None:
    repo = ThreadRepository(session)
    await repo.create_thread(7, 70)
    await session.commit()

    with pytest.raises(ThreadAlreadyExistsError) as exc_info:
        await repo.create_thread(7, 71)
    await session.rollback()

    assert str(exc_info.value) == "Thread already exists"
    assert exc_info.value.data == {"user_id": 7}
    assert (await repo.get_thread(7)).thread_id == 70


async def test_same_thread_id_allowed_for_different_users(session: AsyncSession) -> None:
    repo = ThreadRepository(session)

    await repo.create_thread(7, 70)
    await repo.create_thread(8, 70)
    await session.commit()

    assert (await repo.get_thread(7)).thread_id == 70
    assert (await repo.get_thread(8)).thread_id == 70
