from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.blackwall import Blackwall, BlackwallPunishment, CreateBlackwall, blackwall_table
from songbird.models.management.exceptions import BlackwallAlreadyExistsError, BlackwallNotFoundError
from songbird.utils.logging import get_logger

logger = get_logger(__name__)

STMT_CREATE_BLACKWALL = (
    insert(blackwall_table)
    .values(
        guild_id=bindparam("b_guild_id"),
        channel_id=bindparam("b_channel_id"),
        log_channel_id=bindparam("b_log_channel_id"),
        whitelisted_roles=bindparam("b_whitelisted_roles"),
        punishment=bindparam("b_punishment"),
    )
    .returning(blackwall_table)
)

STMT_GET_BLACKWALL = select(blackwall_table).where(blackwall_table.c.guild_id == bindparam("b_guild_id"))


@dataclass
class BlackwallRepository:
    session: AsyncSession

    async def create(self, input: CreateBlackwall) -> Blackwall:
        params: dict[str, Any] = {
            "b_guild_id": input.guild_id,
            "b_channel_id": input.channel_id,
            "b_log_channel_id": input.log_channel_id,
            "b_whitelisted_roles": input.whitelisted_roles,
            "b_punishment": input.punishment.value,
        }

        try:
            result = await self.session.execute(STMT_CREATE_BLACKWALL, params)
        except IntegrityError as e:
            if "guild_id" in str(e):
                logger.info("Duplicate guild_id detected", guild_id=input.guild_id)
                raise BlackwallAlreadyExistsError(data={"guild_id": input.guild_id}) from e
            logger.exception("Failed to create blackwall config", error=e)
            raise

        return Blackwall.model_validate(result.mappings().one())

    async def increment(self, guild_id: int) -> Blackwall:
        return await self.update(guild_id, banned_count=blackwall_table.c.banned_count + 1)

    async def update(self, guild_id: int, **values: Any) -> Blackwall:
        stmt = (
            update(blackwall_table)
            .where(blackwall_table.c.guild_id == guild_id)
            .values(**{k: v.value if isinstance(v, BlackwallPunishment) else v for k, v in values.items()})
            .returning(blackwall_table)
        )

        result = await self.session.execute(stmt)
        row = result.mappings().one_or_none()

        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": guild_id})

        return Blackwall.model_validate(row)

    async def get(self, guild_id: int) -> Blackwall | None:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_GET_BLACKWALL, params)
        row = result.mappings().one_or_none()

        return Blackwall.model_validate(row) if row is not None else None
