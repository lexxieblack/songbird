from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import GuildMessage, guild_message_table
from songbird.utils.id_factory import make_id

STMT_CREATE_MESSAGE = (
    insert(guild_message_table)
    .values(
        id=bindparam("b_id"),
        guild_id=bindparam("b_guild_id"),
        role=bindparam("b_role"),
        content=bindparam("b_content"),
    )
    .returning(guild_message_table)
)

STMT_GET_NEWEST_MESSAGES = (
    select(guild_message_table)
    .where(guild_message_table.c.guild_id == bindparam("b_guild_id"))
    .order_by(guild_message_table.c.created_at.desc())
    .limit(bindparam("b_limit"))
)

STMT_GET_NEWEST_MESSAGE_ID = (
    select(guild_message_table.c.id)
    .where(guild_message_table.c.guild_id == bindparam("b_guild_id"))
    .order_by(guild_message_table.c.created_at.desc())
    .limit(1)
)

STMT_DELETE_MESSAGE = delete(guild_message_table).where(guild_message_table.c.id == bindparam("b_id"))

STMT_DELETE_MESSAGES = delete(guild_message_table).where(guild_message_table.c.guild_id == bindparam("b_guild_id"))


@dataclass
class GuildMessageRepository:
    session: AsyncSession

    async def create_message(self, guild_id: int, role: MessageRole, content: str) -> GuildMessage:
        params: dict[str, Any] = {
            "b_id": make_id(),
            "b_guild_id": guild_id,
            "b_role": role.value,
            "b_content": content,
        }

        try:
            result = await self.session.execute(STMT_CREATE_MESSAGE, params)
        except IntegrityError as e:
            raise MessageAlreadyExistsError(data={"guild_id": guild_id}) from e

        return GuildMessage.model_validate(result.mappings().one())

    async def get_newest_messages(self, guild_id: int, limit: int = 100) -> list[GuildMessage]:
        params: dict[str, Any] = {
            "b_guild_id": guild_id,
            "b_limit": limit,
        }

        result = await self.session.execute(STMT_GET_NEWEST_MESSAGES, params)
        return [GuildMessage.model_validate(row) for row in result.mappings()]

    async def delete_messages(self, guild_id: int) -> int:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_DELETE_MESSAGES, params)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def delete_last_message(self, guild_id: int) -> None:
        params: dict[str, Any] = {"b_guild_id": guild_id}

        result = await self.session.execute(STMT_GET_NEWEST_MESSAGE_ID, params)
        message_id = result.scalar_one_or_none()
        if message_id is None:
            return

        await self.session.execute(STMT_DELETE_MESSAGE, {"b_id": message_id})
