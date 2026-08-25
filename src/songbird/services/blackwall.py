from cachetools import TTLCache
from structlog import BoundLogger

from songbird.models.management.blackwall import Blackwall, CreateBlackwall
from songbird.services.container import ServiceContainer, get_blackwall_repo, get_session
from songbird.utils.logging import get_logger


class BlackwallService:
    def __init__(
        self,
        container: "ServiceContainer",
        logger: BoundLogger | None = None,
    ):
        self._container = container
        self._cache: TTLCache[int, Blackwall] = TTLCache[int, Blackwall](maxsize=1024, ttl=30)
        self.logger = logger or get_logger(__name__)

    async def create_blackwall(self, guild_id: int, channel_id: int, whitelisted_roles: list[int] | None = None) -> Blackwall:
        input = CreateBlackwall(
            guild_id=guild_id,
            channel_id=channel_id,
            whitelisted_roles=whitelisted_roles or [],
        )

        async with get_session(self._container) as session:
            repo = get_blackwall_repo(session)
            blackwall = await repo.create(input)

        self._cache[guild_id] = blackwall
        return blackwall

    async def increment_blackwall(self, guild_id: int) -> Blackwall:

        async with get_session(self._container) as session:
            repo = get_blackwall_repo(session)
            blackwall = await repo.increment(guild_id)

        self._cache[guild_id] = blackwall

        return blackwall

    async def update_channel(self, guild_id: int, channel_id: int | None) -> Blackwall:
        async with get_session(self._container) as session:
            repo = get_blackwall_repo(session)
            blackwall = await repo.update_channel(guild_id, channel_id)

        self._cache[guild_id] = blackwall
        return blackwall

    async def update_roles(self, guild_id: int, roles: list[int]) -> Blackwall:
        async with get_session(self._container) as session:
            repo = get_blackwall_repo(session)
            blackwall = await repo.update_roles(guild_id, roles)

        self._cache[guild_id] = blackwall
        return blackwall

    async def get_blackwall(self, guild_id: int) -> Blackwall:
        cached = self._cache.get(guild_id)
        if cached is not None:
            return cached

        async with get_session(self._container) as session:
            repo = get_blackwall_repo(session)
            blackwall = await repo.get(guild_id)

        self._cache[guild_id] = blackwall
        return blackwall
