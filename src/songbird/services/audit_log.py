from typing import Any

from structlog import BoundLogger

from songbird.models.management.audit_log import AuditLogAction, CreateAuditLog
from songbird.repositories.management.audit_log import AuditLogRepository
from songbird.utils.logging import get_logger


class AuditLogService:
    def __init__(
        self,
        audit_log_repository: AuditLogRepository,
        logger: BoundLogger | None = None,
    ):
        self.repository = audit_log_repository
        self.logger = logger or get_logger(__name__)

    async def log(
        self,
        action: AuditLogAction,
        actor_id: int | None = None,
        target_id: int | None = None,
        guild_id: int | None = None,
        channel_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        create_audit_log = CreateAuditLog(
            action=action,
            actor_id=actor_id,
            target_id=target_id,
            guild_id=guild_id,
            channel_id=channel_id,
            metadata=metadata or {},
        )
        try:
            await self.repository.create_entry(create_audit_log)
        except Exception:
            raise
