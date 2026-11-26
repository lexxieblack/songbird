import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.blackwall import BlackwallPunishment, CreateBlackwall, blackwall_table
from songbird.models.management.exceptions import BlackwallAlreadyExistsError, BlackwallNotFoundError
from songbird.repositories.management.blackwall import BlackwallRepository
from songbird.services.blackwall import BlackwallService
from songbird.services.container import ServiceContainer

pytestmark = pytest.mark.db


async def test_create_persists_and_caches(db_container: ServiceContainer, session: AsyncSession) -> None:
    service = BlackwallService(db_container)

    created = await service.create_blackwall(1, channel_id=2, log_channel_id=3, whitelisted_roles=[4])

    assert created.guild_id == 1
    assert created.channel_id == 2
    assert created.log_channel_id == 3
    assert created.whitelisted_roles == [4]
    assert created.banned_count == 0
    assert created.punishment is BlackwallPunishment.BAN
    assert await BlackwallRepository(session).get(1) == created


async def test_get_reads_database_then_serves_from_cache(db_container: ServiceContainer, session: AsyncSession) -> None:
    repo = BlackwallRepository(session)
    created = await repo.create(CreateBlackwall(guild_id=1, channel_id=None))
    await session.commit()

    service = BlackwallService(db_container)
    first = await service.get_blackwall(1)
    await session.execute(delete(blackwall_table))
    await session.commit()

    assert first == created
    assert await service.get_blackwall(1) is first


async def test_get_missing_returns_none(db_container: ServiceContainer) -> None:
    assert await BlackwallService(db_container).get_blackwall(999) is None


async def test_get_missing_is_cached(db_container: ServiceContainer, session: AsyncSession) -> None:
    service = BlackwallService(db_container)
    assert await service.get_blackwall(999) is None

    await BlackwallRepository(session).create(CreateBlackwall(guild_id=999, channel_id=None))
    await session.commit()

    assert await service.get_blackwall(999) is None


async def test_increment_counts_bans(db_container: ServiceContainer) -> None:
    service = BlackwallService(db_container)
    await service.create_blackwall(1)

    assert (await service.increment_blackwall(1)).banned_count == 1
    assert (await service.increment_blackwall(1)).banned_count == 2


async def test_increment_missing_raises(db_container: ServiceContainer) -> None:
    with pytest.raises(BlackwallNotFoundError):
        await BlackwallService(db_container).increment_blackwall(999)


async def test_updates_persist_and_refresh_cache(db_container: ServiceContainer, session: AsyncSession) -> None:
    service = BlackwallService(db_container)
    await service.create_blackwall(1)

    await service.update(1, channel_id=20)
    await service.update(1, log_channel_id=30)
    await service.update(1, whitelisted_roles=[7, 8])
    updated = await service.update(1, punishment=BlackwallPunishment.KICK)

    assert updated.channel_id == 20
    assert updated.log_channel_id == 30
    assert updated.whitelisted_roles == [7, 8]
    assert updated.punishment is BlackwallPunishment.KICK

    stored = await BlackwallRepository(session).get(1)
    assert stored is not None
    assert stored.channel_id == 20
    assert stored.log_channel_id == 30
    assert stored.whitelisted_roles == [7, 8]
    assert stored.punishment is BlackwallPunishment.KICK
    assert await service.get_blackwall(1) is updated


async def test_update_missing_raises(db_container: ServiceContainer) -> None:
    with pytest.raises(BlackwallNotFoundError):
        await BlackwallService(db_container).update(999, channel_id=1)


async def test_duplicate_guild_raises(db_container: ServiceContainer) -> None:
    service = BlackwallService(db_container)
    await service.create_blackwall(1)

    with pytest.raises(BlackwallAlreadyExistsError):
        await service.create_blackwall(1)
