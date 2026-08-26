from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field
from sqlalchemy import BigInteger, Column, DateTime, PrimaryKeyConstraint, Table, func
from sqlalchemy import Enum as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from songbird.models._base_db_model import BaseDBModel
from songbird.models.management.base import metadata


class AuditLogAction(Enum):
    BLACKWALL_BAN = "blackwall_ban"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value


MessageRoleEnum = PGEnum(
    *[role.value for role in AuditLogAction],
    name="audit_log_action",
    schema="management",
    create_constraint=True,
    validate_strings=True,
)

audit_log_table = Table(
    "audit_log",
    metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    Column("action", MessageRoleEnum, nullable=False),
    Column("actor_id", BigInteger, nullable=True),
    Column("target_id", BigInteger, nullable=True),
    Column("guild_id", BigInteger, nullable=True),
    Column("channel_id", BigInteger, nullable=True),
    Column("metadata", JSONB, nullable=False, server_default="'{}'::jsonb"),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    PrimaryKeyConstraint("id"),
)


class _AuditLogBase(BaseDBModel):
    action: AuditLogAction
    actor_id: int | None
    target_id: int | None
    guild_id: int | None
    channel_id: int | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditLog(_AuditLogBase):
    id: UUID
    created_at: datetime


class CreateAuditLog(_AuditLogBase):
    model_config = ConfigDict(frozen=True)
