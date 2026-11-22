import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import UserInfoNotFoundError
from songbird.models.management.exceptions import UserBanAlreadyExistsError, UserBanNotFoundError
from songbird.repositories.chat.guild_message import GuildMessageRepository
from songbird.repositories.chat.message import MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.repositories.management.guild_ban import GuildBanRepository
from songbird.repositories.management.user_ban import UserBanRepository
from songbird.services.container import ServiceContainer
from songbird.services.management import BanEnforcementService

pytestmark = pytest.mark.db


async def test_check_user_banned_reads_then_caches(db_container: ServiceContainer, session: AsyncSession) -> None:
    service = BanEnforcementService(db_container)
    assert await service.check_user_banned(1) is False

    await UserBanRepository(session).create_ban(1)
    await session.commit()

    assert await service.check_user_banned(1) is False
    assert await BanEnforcementService(db_container).check_user_banned(1) is True


async def test_check_guild_banned_reads_then_caches(db_container: ServiceContainer, session: AsyncSession) -> None:
    service = BanEnforcementService(db_container)
    assert await service.check_guild_banned(1) is False

    await GuildBanRepository(session).create_ban(1)
    await session.commit()

    assert await service.check_guild_banned(1) is False
    assert await BanEnforcementService(db_container).check_guild_banned(1) is True


async def test_ban_user_deletes_history_and_info(db_container: ServiceContainer, session: AsyncSession) -> None:
    messages = MessageRepository(session)
    await messages.create_message(1, MessageRole.USER, "hello")
    await messages.create_message(1, MessageRole.MODEL, "hi")
    await UserInfoRepository(session).create_user_info(1, "profile")
    await session.commit()

    ban = await BanEnforcementService(db_container).ban_user(1, reason="spam")

    assert ban.user_id == 1
    assert ban.reason == "spam"
    assert await MessageRepository(session).get_newest_messages(1) == []
    with pytest.raises(UserInfoNotFoundError):
        await UserInfoRepository(session).get_user_info(1)


async def test_ban_user_sets_cache_and_duplicate_raises(db_container: ServiceContainer) -> None:
    service = BanEnforcementService(db_container)
    await service.ban_user(1)

    assert await service.check_user_banned(1) is True
    with pytest.raises(UserBanAlreadyExistsError):
        await service.ban_user(1)


async def test_ban_guild_deletes_history_and_sets_cache(db_container: ServiceContainer, session: AsyncSession) -> None:
    guild_messages = GuildMessageRepository(session)
    await guild_messages.create_message(1, MessageRole.USER, "hello")
    await session.commit()

    ban = await BanEnforcementService(db_container).ban_guild(1, reason="raid")
    service = BanEnforcementService(db_container)

    assert ban.reason == "raid"
    assert await GuildMessageRepository(session).get_newest_messages(1) == []
    assert await service.check_guild_banned(1) is True


async def test_unban_user_clears_cache(db_container: ServiceContainer, session: AsyncSession) -> None:
    await UserBanRepository(session).create_ban(1)
    await session.commit()
    service = BanEnforcementService(db_container)
    assert await service.check_user_banned(1) is True

    await service.unban_user(1)

    assert await service.check_user_banned(1) is False
    with pytest.raises(UserBanNotFoundError):
        await UserBanRepository(session).get_ban(1)


async def test_unban_missing_raises(db_container: ServiceContainer) -> None:
    with pytest.raises(UserBanNotFoundError):
        await BanEnforcementService(db_container).unban_user(999)


async def test_unban_guild_clears_cache(db_container: ServiceContainer, session: AsyncSession) -> None:
    await GuildBanRepository(session).create_ban(1)
    await session.commit()
    service = BanEnforcementService(db_container)
    assert await service.check_guild_banned(1) is True

    await service.unban_guild(1)

    assert await service.check_guild_banned(1) is False


async def test_list_and_startup_ids(db_container: ServiceContainer, session: AsyncSession) -> None:
    await UserBanRepository(session).create_ban(1)
    await UserBanRepository(session).create_ban(2)
    await GuildBanRepository(session).create_ban(10)
    await GuildBanRepository(session).create_ban(20)
    await session.commit()

    service = BanEnforcementService(db_container)

    assert {ban.user_id for ban in await service.list_user_bans()} == {1, 2}
    assert {ban.guild_id for ban in await service.list_guild_bans()} == {10, 20}
    assert await service.get_banned_guild_ids() == {10, 20}
