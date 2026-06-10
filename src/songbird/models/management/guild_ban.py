from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, PrimaryKeyConstraint, Table, Text, func

from songbird.models._base_db_model import BaseDBModel
from songbird.models.management.base import metadata

guild_ban_table = Table(
    "guild_ban",
    metadata,
    Column("guild_id", BigInteger, primary_key=True),
    Column("reason", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    PrimaryKeyConstraint("guild_id"),
)


class GuildBan(BaseDBModel):
    guild_id: int
    reason: str | None
    created_at: datetime
