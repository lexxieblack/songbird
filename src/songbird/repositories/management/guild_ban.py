from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import GuildBanAlreadyExistsError, GuildBanNotFoundError
from songbird.models.management.guild_ban import GuildBan, guild_ban_table


@dataclass
class GuildBanRepository:
    session: AsyncSession

    async def create_ban(self, guild_id: int, reason: str | None = None) -> GuildBan:
        stmt = (
            insert(guild_ban_table)
            .values(
                guild_id=guild_id,
                reason=reason,
            )
            .returning(guild_ban_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise GuildBanAlreadyExistsError(data={"guild_id": guild_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create guild ban")

        return GuildBan.model_validate(row)

    async def get_ban(self, guild_id: int) -> GuildBan:
        result = await self.session.execute(select(guild_ban_table).where(guild_ban_table.c.guild_id == guild_id))
        row = result.one_or_none()

        if row is None:
            raise GuildBanNotFoundError(data={"guild_id": guild_id})

        return GuildBan.model_validate(row)

    async def is_banned(self, guild_id: int) -> bool:
        result = await self.session.execute(select(guild_ban_table).where(guild_ban_table.c.guild_id == guild_id))
        return result.one_or_none() is not None

    async def delete_ban(self, guild_id: int) -> None:
        stmt = delete(guild_ban_table).where(guild_ban_table.c.guild_id == guild_id)
        result = await self.session.execute(stmt)

        if result.rowcount == 0:  # type: ignore
            raise GuildBanNotFoundError(data={"guild_id": guild_id})

    async def list_bans(self) -> list[GuildBan]:
        result = await self.session.execute(select(guild_ban_table).order_by(guild_ban_table.c.created_at.desc()))
        return [GuildBan.model_validate(row) for row in result.fetchall()]
