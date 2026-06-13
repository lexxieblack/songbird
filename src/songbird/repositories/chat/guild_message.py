from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import GuildMessage, guild_message_table
from songbird.utils.id_factory import make_id


@dataclass
class GuildMessageRepository:
    session: AsyncSession

    async def create_message(self, guild_id: int, role: MessageRole, content: str) -> GuildMessage:
        stmt = (
            insert(guild_message_table)
            .values(
                id=make_id(),
                guild_id=guild_id,
                role=role.value,
                content=content,
            )
            .returning(guild_message_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise MessageAlreadyExistsError(data={"guild_id": guild_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create GuildMessage")

        return GuildMessage.model_validate(row)

    async def get_newest_messages(self, guild_id: int, limit: int = 100) -> list[GuildMessage]:
        stmt = (
            select(guild_message_table)
            .where(guild_message_table.c.guild_id == guild_id)
            .order_by(guild_message_table.c.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.fetchall()
        return [GuildMessage.model_validate(row) for row in rows]

    async def delete_messages(self, guild_id: int) -> int:
        stmt = delete(guild_message_table).where(guild_message_table.c.guild_id == guild_id)
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore

    async def delete_last_message(self, guild_id: int) -> None:
        messages = await self.get_newest_messages(guild_id, limit=1)
        if not messages or len(messages) == 0:
            return

        stmt = (
            delete(guild_message_table)
            .where(guild_message_table.c.guild_id == guild_id)
            .where(guild_message_table.c.id == messages[0].id)
        )
        await self.session.execute(stmt)
        return
