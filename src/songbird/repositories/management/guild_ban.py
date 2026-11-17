from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, exists, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import GuildBanAlreadyExistsError, GuildBanNotFoundError
from songbird.models.management.guild_ban import GuildBan, guild_ban_table

STMT_CREATE_BAN = (
    insert(guild_ban_table)
    .values(
        guild_id=bindparam("b_guild_id"),
        reason=bindparam("b_reason"),
    )
    .returning(guild_ban_table)
)

STMT_GET_BAN = select(guild_ban_table).where(guild_ban_table.c.guild_id == bindparam("b_guild_id"))

STMT_IS_BANNED = select(exists().where(guild_ban_table.c.guild_id == bindparam("b_guild_id")))

STMT_DELETE_BAN = (
    delete(guild_ban_table).where(guild_ban_table.c.guild_id == bindparam("b_guild_id")).returning(guild_ban_table.c.guild_id)
)

STMT_LIST_BANS = select(guild_ban_table).order_by(guild_ban_table.c.created_at.desc())


@dataclass
class GuildBanRepository:
    session: AsyncSession

    async def create_ban(self, guild_id: int, reason: str | None = None) -> GuildBan:
        params: dict[str, Any] = {
            "b_guild_id": guild_id,
            "b_reason": reason,
        }

        try:
            result = await self.session.execute(STMT_CREATE_BAN, params)
        except IntegrityError as e:
            raise GuildBanAlreadyExistsError(data={"guild_id": guild_id}) from e

        return GuildBan.model_validate(result.mappings().one())

    async def get_ban(self, guild_id: int) -> GuildBan:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_GET_BAN, params)
        row = result.mappings().one_or_none()

        if row is None:
            raise GuildBanNotFoundError(data={"guild_id": guild_id})

        return GuildBan.model_validate(row)

    async def is_banned(self, guild_id: int) -> bool:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_IS_BANNED, params)
        return result.scalar_one()

    async def delete_ban(self, guild_id: int) -> None:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_DELETE_BAN, params)
        if result.mappings().one_or_none() is None:
            raise GuildBanNotFoundError(data={"guild_id": guild_id})

    async def list_bans(self) -> list[GuildBan]:
        result = await self.session.execute(STMT_LIST_BANS)
        return [GuildBan.model_validate(row) for row in result.mappings()]
