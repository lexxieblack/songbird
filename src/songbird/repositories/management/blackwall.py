from dataclasses import dataclass

from sqlalchemy import bindparam, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.blackwall import Blackwall, CreateBlackwall, blackwall_table
from songbird.models.management.exceptions import BlackwallAlreadyExistsError, BlackwallNotFoundError
from songbird.utils.logging import get_logger

logger = get_logger(__name__)

STMT_CREATE_BLACKWALL = (
    insert(blackwall_table)
    .values(
        b_guild_id=bindparam("b_guild_id"),
        b_channel_id=bindparam("b_channel_id"),
        b_whitelisted_roles=bindparam("b_whitelisted_roles"),
    )
    .returning(blackwall_table)
)

STMT_INCREMENT_BANNED = (
    update(blackwall_table)
    .where(blackwall_table.c.guild_id == bindparam("b_guild_id"))
    .values(banned_count=blackwall_table.c.banned_count + 1)
    .returning(blackwall_table)
)

STMT_UPDATE_CHANNEL = (
    update(blackwall_table)
    .where(blackwall_table.c.guild_id == bindparam("b_guild_id"))
    .values(b_channel_id=bindparam("b_channel_id"))
    .returning(blackwall_table)
)

STMT_UPDATE_ROLES = (
    update(blackwall_table)
    .where(blackwall_table.c.guild_id == bindparam("b_guild_id"))
    .values(b_whitelisted_roles=bindparam("b_whitelisted_roles"))
    .returning(blackwall_table)
)

STMT_GET_BLACKWALL = select(blackwall_table).where(blackwall_table.c.guild_id == bindparam("b_guild_id"))


@dataclass
class BlackwallRepository:
    session: AsyncSession

    async def create(self, input: CreateBlackwall) -> Blackwall:
        params = {
            "b_guild_id": input.guild_id,
            "b_channel_id": input.channel_id,
            "b_whitelisted_roles": input.whitelisted_roles,
        }

        try:
            result = await self.session.execute(STMT_CREATE_BLACKWALL, params)
        except IntegrityError as e:
            if "guild_id" in str(e):
                logger.info("Duplicate guild_id detected", guild_id=input.guild_id)
                raise BlackwallAlreadyExistsError(data={"guild_id": input.guild_id}) from e
            logger.exception("Failed to create blackwall config", error=e)
            raise

        row = result.mappings().first()
        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": input.guild_id})

        return Blackwall.model_validate(row)

    async def increment(self, guild_id: int) -> Blackwall:
        params = {
            "b_guild_id": guild_id,
        }

        try:
            result = await self.session.execute(STMT_INCREMENT_BANNED, params)
        except Exception as e:
            logger.exception("Failed to create blackwall config", error=e)
            raise

        row = result.mappings().first()

        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": guild_id})

        return Blackwall.model_validate(row)

    async def update_channel(self, guild_id: int, channel_id: int) -> Blackwall:
        params = {
            "b_guild_id": guild_id,
            "b_channel_id": channel_id,
        }

        try:
            result = await self.session.execute(STMT_UPDATE_CHANNEL, params)
        except Exception as e:
            logger.exception("Failed to update blackwall config", error=e)
            raise

        row = result.mappings().first()

        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": guild_id})

        return Blackwall.model_validate(row)

    async def update_roles(self, guild_id: int, roles: list[int]) -> Blackwall:
        params = {
            "b_guild_id": guild_id,
            "b_whitelisted_roles": roles,
        }

        try:
            result = await self.session.execute(STMT_UPDATE_ROLES, params)
        except Exception as e:
            logger.exception("Failed to update blackwall config", error=e)
            raise

        row = result.mappings().first()

        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": guild_id})

        return Blackwall.model_validate(row)

    async def get(self, guild_id: int) -> Blackwall:
        params = {
            "b_guild_id": guild_id,
        }
        result = await self.session.execute(STMT_GET_BLACKWALL, params)
        row = result.mappings().first()

        if row is None:
            raise BlackwallNotFoundError(data={"guild_id": guild_id})

        return Blackwall.model_validate(row)
