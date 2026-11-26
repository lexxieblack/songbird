from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy import Table, delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models._base_db_model import BaseDBModel
from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import GuildMessage, guild_message_table
from songbird.models.chat.message import Message, message_table
from songbird.utils.id_factory import make_id


@dataclass
class BaseMessageRepository[T: BaseDBModel]:
    """Shared SQL for the two history tables, which differ only by their key column."""

    session: AsyncSession

    table: ClassVar[Table]
    model: ClassVar[type[T]]
    key: ClassVar[str]

    async def create_message(self, key: int, role: MessageRole, content: str) -> T:
        stmt = insert(self.table).values(id=make_id(), role=role.value, content=content, **{self.key: key}).returning(self.table)

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise MessageAlreadyExistsError(data={self.key: key}) from e

        return self.model.model_validate(result.mappings().one())

    async def get_newest_messages(self, key: int, limit: int = 100) -> list[T]:
        stmt = (
            select(self.table)
            .where(self.table.c[self.key] == key)
            .order_by(self.table.c.created_at.desc(), self.table.c.id.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return [self.model.model_validate(row) for row in result.mappings()]

    async def get_all_messages(self, key: int, limit: int | None = None) -> list[T]:
        stmt = (
            select(self.table).where(self.table.c[self.key] == key).order_by(self.table.c.created_at.asc(), self.table.c.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return [self.model.model_validate(row) for row in result.mappings()]

    async def delete_messages(self, key: int) -> int:
        result = await self.session.execute(delete(self.table).where(self.table.c[self.key] == key))
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def delete_last_message(self, key: int) -> None:
        stmt = (
            select(self.table.c.id)
            .where(self.table.c[self.key] == key)
            .order_by(self.table.c.created_at.desc(), self.table.c.id.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        message_id = result.scalar_one_or_none()
        if message_id is None:
            return

        await self.session.execute(delete(self.table).where(self.table.c.id == message_id))


class MessageRepository(BaseMessageRepository[Message]):
    table = message_table
    model = Message
    key = "user_id"


class GuildMessageRepository(BaseMessageRepository[GuildMessage]):
    table = guild_message_table
    model = GuildMessage
    key = "guild_id"
