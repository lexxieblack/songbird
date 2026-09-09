from datetime import datetime
from enum import Enum

from pydantic import ConfigDict, Field
from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Integer, PrimaryKeyConstraint, Table, func
from sqlalchemy import Enum as PGEnum

from songbird.models._base_db_model import BaseDBModel
from songbird.models.management.base import metadata


class BlackwallPunishment(Enum):
    LOG = "log"
    KICK = "kick"
    BAN = "ban"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value


PunishmentType = PGEnum(
    *[punishment.value for punishment in BlackwallPunishment],
    name="blackwall_punishment",
    schema="management",
    create_constraint=True,
    validate_strings=True,
)

blackwall_table = Table(
    "blackwall",
    metadata,
    Column("guild_id", BigInteger, primary_key=True),
    Column("channel_id", BigInteger, nullable=True),
    Column("log_channel_id", BigInteger, nullable=True),
    Column("whitelisted_roles", ARRAY(BigInteger), nullable=False, default=[]),
    Column("banned_count", Integer, nullable=False, default=0),
    Column("punishment", PunishmentType, nullable=False, default="ban"),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()),
    PrimaryKeyConstraint("guild_id"),
)


class _BlackwallBase(BaseDBModel):
    guild_id: int
    channel_id: int | None
    log_channel_id: int | None = None
    whitelisted_roles: list[int] = Field(default_factory=list)
    punishment: BlackwallPunishment = BlackwallPunishment.BAN


class Blackwall(_BlackwallBase):
    banned_count: int
    created_at: datetime
    updated_at: datetime


class CreateBlackwall(_BlackwallBase):
    model_config = ConfigDict(frozen=True)
