from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from songbird.models.management.guild_ban import GuildBan
from songbird.models.management.user_ban import UserBan
from songbird.repositories.chat.message import GuildMessageRepository, MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.repositories.management.guild_ban import GuildBanRepository
from songbird.repositories.management.user_ban import UserBanRepository
from songbird.services.container import get_session


class BanEnforcementService:
    """Long-lived service for ban enforcement with an in-memory TTL cache.

    Provides ban CRUD operations, existence checks with caching, and
    automatic deletion of conversation history on ban creation.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self._user_cache: TTLCache[int, bool] = TTLCache[int, bool](maxsize=1024, ttl=60)
        self._guild_cache: TTLCache[int, bool] = TTLCache[int, bool](maxsize=1024, ttl=60)

    async def check_user_banned(self, user_id: int) -> bool:
        """Check whether a user is banned, using the TTL cache."""
        cached = self._user_cache.get(user_id)
        if cached is not None:
            return cached

        async with get_session(self) as session:
            repo = UserBanRepository(session)
            banned = await repo.is_banned(user_id)

        self._user_cache[user_id] = banned
        return banned

    async def check_guild_banned(self, guild_id: int) -> bool:
        """Check whether a guild is banned, using the TTL cache."""
        cached = self._guild_cache.get(guild_id)
        if cached is not None:
            return cached

        async with get_session(self) as session:
            repo = GuildBanRepository(session)
            banned = await repo.is_banned(guild_id)

        self._guild_cache[guild_id] = banned
        return banned

    async def ban_user(self, user_id: int, reason: str | None = None) -> UserBan:
        """Ban a user, delete all their stored data, and invalidate the cache."""
        async with get_session(self) as session:
            ban_repo = UserBanRepository(session)
            user_ban = await ban_repo.create_ban(user_id, reason=reason)

            message_repo = MessageRepository(session)
            await message_repo.delete_messages(user_id)

            user_info_repo = UserInfoRepository(session)
            await user_info_repo.delete_user_info(user_id)

        self._user_cache[user_id] = True
        return user_ban

    async def ban_guild(self, guild_id: int, reason: str | None = None) -> GuildBan:
        """Ban a guild, delete its conversation history, and invalidate the cache."""
        async with get_session(self) as session:
            ban_repo = GuildBanRepository(session)
            guild_ban = await ban_repo.create_ban(guild_id, reason=reason)

            message_repo = GuildMessageRepository(session)
            await message_repo.delete_messages(guild_id)

        self._guild_cache[guild_id] = True
        return guild_ban

    async def unban_user(self, user_id: int) -> None:
        """Remove a user ban and invalidate the cache."""
        async with get_session(self) as session:
            repo = UserBanRepository(session)
            await repo.delete_ban(user_id)

        self._user_cache.pop(user_id, None)

    async def unban_guild(self, guild_id: int) -> None:
        """Remove a guild ban and invalidate the cache."""
        async with get_session(self) as session:
            repo = GuildBanRepository(session)
            await repo.delete_ban(guild_id)

        self._guild_cache.pop(guild_id, None)

    async def list_user_bans(self) -> list[UserBan]:
        """Return all user bans."""
        async with get_session(self) as session:
            repo = UserBanRepository(session)
            return await repo.list_bans()

    async def list_guild_bans(self) -> list[GuildBan]:
        """Return all guild bans."""
        async with get_session(self) as session:
            repo = GuildBanRepository(session)
            return await repo.list_bans()

    async def get_banned_guild_ids(self) -> set[int]:
        """Return a set of all banned guild IDs (for startup sweep)."""
        async with get_session(self) as session:
            repo = GuildBanRepository(session)
            bans = await repo.list_bans()
            return {ban.guild_id for ban in bans}
