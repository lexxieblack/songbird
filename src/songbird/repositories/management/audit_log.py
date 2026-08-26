from dataclasses import dataclass

from sqlalchemy import bindparam, insert
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.audit_log import AuditLog, CreateAuditLog, audit_log_table
from songbird.utils.id_factory import make_id
from songbird.utils.logging import get_logger

logger = get_logger(__name__)

B_PARAM_ID = bindparam("b_id", type_=PGUUID(as_uuid=True))


STMT_CREATE_AUDIT_LOG = (
    insert(audit_log_table)
    .values(
        id=B_PARAM_ID,
        action=bindparam("b_action"),
        actor_id=bindparam("b_actor_id"),
        target_id=bindparam("b_target_id"),
        guild_id=bindparam("b_guild_id"),
        channel_id=bindparam("b_channel_id"),
        metadata=bindparam("b_metadata"),
    )
    .returning(audit_log_table)
)


@dataclass
class AuditLogRepository:
    session: AsyncSession

    async def create(self, log: CreateAuditLog) -> AuditLog:
        params = {
            "b_id": make_id(),
            "b_action": log.action.value,
            "b_actor_id": log.actor_id,
            "b_target_id": log.target_id,
            "b_guild_id": log.guild_id,
            "b_channel_id": log.channel_id,
            "b_metadata": log.metadata,
        }
        try:
            result = await self.session.execute(STMT_CREATE_AUDIT_LOG, params)
        except Exception as e:
            logger.exception("Failed to create audit log", exc_info=e)
            raise

        row = result.mappings().one()
        if row is None:
            raise ValueError("Failed to create audit log")

        return AuditLog.model_validate(row)
