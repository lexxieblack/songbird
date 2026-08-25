from datetime import datetime

from pydantic import ConfigDict, Field
from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Integer, PrimaryKeyConstraint, Table, func

from songbird.models._base_db_model import BaseDBModel
from songbird.models.management.base import metadata

blackwall_table = Table(
    "blackwall",
    metadata,
    Column("guild_id", BigInteger, primary_key=True),
    Column("channel_id", BigInteger, nullable=True),
    Column("whitelisted_roles", ARRAY(BigInteger), nullable=False, default=[]),
    Column("banned_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()),
    PrimaryKeyConstraint("guild_id"),
)


class _BlackwallBase(BaseDBModel):
    guild_id: int
    channel_id: int | None
    whitelisted_roles: list[int] = Field(default_factory=list)

class Blackwall(_BlackwallBase):
    banned_count: int
    created_at: datetime
    updated_at: datetime

class CreateBlackwall(_BlackwallBase):
    model_config = ConfigDict(frozen=True)
