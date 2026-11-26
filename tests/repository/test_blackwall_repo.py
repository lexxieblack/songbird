import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.blackwall import BlackwallPunishment, CreateBlackwall
from songbird.models.management.exceptions import BlackwallAlreadyExistsError, BlackwallNotFoundError
from songbird.repositories.management.blackwall import BlackwallRepository

pytestmark = pytest.mark.db


async def test_create_applies_defaults(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    created = await repo.create(CreateBlackwall(guild_id=1, channel_id=None))
    await session.commit()

    assert created.channel_id is None
    assert created.log_channel_id is None
    assert created.whitelisted_roles == []
    assert created.banned_count == 0
    assert created.punishment is BlackwallPunishment.BAN
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None


async def test_create_stores_provided_values(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    await repo.create(
        CreateBlackwall(
            guild_id=1,
            channel_id=10,
            log_channel_id=20,
            whitelisted_roles=[3, 4],
            punishment=BlackwallPunishment.KICK,
        )
    )
    await session.commit()

    fetched = await repo.get(1)
    assert fetched is not None
    assert (fetched.channel_id, fetched.log_channel_id) == (10, 20)
    assert fetched.whitelisted_roles == [3, 4]
    assert fetched.punishment is BlackwallPunishment.KICK


async def test_get_missing_returns_none(session: AsyncSession) -> None:
    assert await BlackwallRepository(session).get(404) is None


async def test_create_duplicate_translates_integrity_error(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    await repo.create(CreateBlackwall(guild_id=1, channel_id=10))
    await session.commit()

    with pytest.raises(BlackwallAlreadyExistsError) as exc_info:
        await repo.create(CreateBlackwall(guild_id=1, channel_id=11))
    await session.rollback()

    assert str(exc_info.value) == "Blackwall config already exists for this guild"
    assert exc_info.value.data == {"guild_id": 1}
    fetched = await repo.get(1)
    assert fetched is not None
    assert fetched.channel_id == 10


async def test_updates_change_single_column(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    await repo.create(CreateBlackwall(guild_id=1, channel_id=10, log_channel_id=20, whitelisted_roles=[3]))
    await session.commit()

    assert (await repo.update(1, channel_id=11)).channel_id == 11
    assert (await repo.update(1, log_channel_id=21)).log_channel_id == 21
    assert (await repo.update(1, whitelisted_roles=[5, 6])).whitelisted_roles == [5, 6]
    assert (await repo.update(1, punishment=BlackwallPunishment.KICK)).punishment is BlackwallPunishment.KICK
    await session.commit()

    fetched = await repo.get(1)
    assert fetched is not None
    assert (fetched.channel_id, fetched.log_channel_id) == (11, 21)
    assert fetched.whitelisted_roles == [5, 6]
    assert fetched.punishment is BlackwallPunishment.KICK


async def test_update_roles_accepts_empty_list(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    await repo.create(CreateBlackwall(guild_id=1, channel_id=10, whitelisted_roles=[3]))

    assert (await repo.update(1, whitelisted_roles=[])).whitelisted_roles == []


async def test_increment_returns_new_count(session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    await repo.create(CreateBlackwall(guild_id=1, channel_id=10))
    await session.commit()

    assert (await repo.increment(1)).banned_count == 1
    assert (await repo.increment(1)).banned_count == 2
    await session.commit()

    fetched = await repo.get(1)
    assert fetched is not None
    assert fetched.banned_count == 2


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("increment", {}),
        ("update", {"channel_id": None}),
        ("update", {"punishment": BlackwallPunishment.LOG}),
    ],
)
async def test_missing_guild_raises_not_found(session: AsyncSession, method: str, kwargs: dict[str, object]) -> None:
    repo = BlackwallRepository(session)

    with pytest.raises(BlackwallNotFoundError) as exc_info:
        await getattr(repo, method)(404, **kwargs)

    assert str(exc_info.value) == "Blackwall config not found for this guild"
    assert exc_info.value.data == {"guild_id": 404}
