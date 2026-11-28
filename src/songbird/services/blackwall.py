from typing import Any

from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import BoundLogger

from songbird.models.management.blackwall import Blackwall, CreateBlackwall
from songbird.repositories.management.blackwall import BlackwallRepository
from songbird.services.container import get_session
from songbird.utils.logging import get_logger


class BlackwallService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        logger: BoundLogger | None = None,
    ):
        self.session_factory = session_factory
        self._cache: TTLCache[int, Blackwall | None] = TTLCache[int, Blackwall | None](maxsize=1024, ttl=30)
        self.logger = logger or get_logger(__name__)

    async def create_blackwall(
        self,
        guild_id: int,
        channel_id: int | None = None,
        log_channel_id: int | None = None,
        whitelisted_roles: list[int] | None = None,
    ) -> Blackwall:
        input = CreateBlackwall(
            guild_id=guild_id,
            channel_id=channel_id,
            log_channel_id=log_channel_id,
            whitelisted_roles=whitelisted_roles or [],
        )

        async with get_session(self) as session:
            repo = BlackwallRepository(session)
            blackwall = await repo.create(input)

        self._cache[guild_id] = blackwall
        return blackwall

    async def increment_blackwall(self, guild_id: int) -> Blackwall:

        async with get_session(self) as session:
            repo = BlackwallRepository(session)
            blackwall = await repo.increment(guild_id)

        self._cache[guild_id] = blackwall

        return blackwall

    async def update(self, guild_id: int, **fields: Any) -> Blackwall:
        async with get_session(self) as session:
            repo = BlackwallRepository(session)
            blackwall = await repo.update(guild_id, **fields)

        self._cache[guild_id] = blackwall
        return blackwall

    async def get_blackwall(self, guild_id: int) -> Blackwall | None:
        # Negative results are cached too: unconfigured guilds would otherwise query on every message.
        if guild_id in self._cache:
            return self._cache[guild_id]

        async with get_session(self) as session:
            repo = BlackwallRepository(session)
            blackwall = await repo.get(guild_id)

        self._cache[guild_id] = blackwall
        return blackwall
