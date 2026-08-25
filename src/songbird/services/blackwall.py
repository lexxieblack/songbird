from typing import Any, cast

from cachetools import TTLCache
from structlog import BoundLogger

from songbird.models.management.audit_log import AuditLogAction
from songbird.models.management.blackwall import Blackwall, CreateBlackwall
from songbird.repositories.management.blackwall import BlackwallRepository
from songbird.services.audit_log import AuditLogService
from songbird.utils.logging import get_logger


class BlackwallService:
    def __init__(
        self,
        blackwall_repository: BlackwallRepository,
        audit_log_service: AuditLogService,
        logger: BoundLogger | None = None,
    ):
        self.repository = blackwall_repository
        self.audit_log_service = audit_log_service
        self._cache: TTLCache[int, object] = TTLCache[int, object](maxsize=1024, ttl=30)
        self.logger = logger or get_logger(__name__)

    async def create_blackwall(self, guild_id: int, channel_id: int, whitelisted_roles: list[int] | None) -> Blackwall:
        input = CreateBlackwall(
            guild_id=guild_id,
            channel_id=channel_id,
            whitelisted_roles=whitelisted_roles or [],
        )

        blackwall = await self.repository.create(input)
        self._cache[guild_id] = blackwall
        return blackwall

    async def increment_blackwall(self, target_id: int, guild_id: int, metadata: dict[str, Any]) -> Blackwall:
        blackwall = await self.repository.increment(guild_id)
        self._cache[guild_id] = blackwall

        await self.audit_log_service.log(
            AuditLogAction.BLACKWALL_BAN,
            target_id=target_id,
            guild_id=guild_id,
            metadata=metadata,
        )

        return blackwall

    async def update_channel(self, guild_id: int, channel_id: int) -> Blackwall:
        blackwall = await self.repository.update_channel(guild_id, channel_id)
        self._cache[guild_id] = blackwall
        return blackwall

    async def update_roles(self, guild_id: int, roles: list[int]) -> Blackwall:
        blackwall = await self.repository.update_roles(guild_id, roles)
        self._cache[guild_id] = blackwall
        return blackwall

    async def get_blackwall(self, guild_id: int) -> Blackwall:
        cached = self._cache.get(guild_id)
        if cached is not None:
            return cast(Blackwall, cached)

        blackwall = await self.repository.get(guild_id)
        self._cache[guild_id] = blackwall
        return blackwall
