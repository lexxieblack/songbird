from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Column, DateTime, PrimaryKeyConstraint, Table, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from songbird.models._base_db_model import BaseDBModel
from songbird.models.chat.base import MessageRole, MessageRoleEnum, metadata

guild_message_table = Table(
    "guild_message",
    metadata,
    Column("id", PGUUID, primary_key=True),
    Column("guild_id", BigInteger, nullable=False),
    Column("role", MessageRoleEnum, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    PrimaryKeyConstraint("id"),
)


class GuildMessage(BaseDBModel):
    id: UUID
    guild_id: int
    role: MessageRole
    content: str
    created_at: datetime
