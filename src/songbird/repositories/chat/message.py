from dataclasses import dataclass

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.message import Message, UserStats, message_table
from songbird.utils.id_factory import make_id


@dataclass
class MessageRepository:
    session: AsyncSession

    async def create_message(self, user_id: int, role: MessageRole, content: str) -> Message:
        stmt = (
            insert(message_table)
            .values(
                id=make_id(),
                user_id=user_id,
                role=role.value,
                content=content,
            )
            .returning(message_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise MessageAlreadyExistsError(data={"user_id": user_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create message")

        return Message.model_validate(row)

    async def get_newest_messages(self, user_id: int, limit: int = 100) -> list[Message]:
        stmt = (
            select(message_table).where(message_table.c.user_id == user_id).order_by(message_table.c.created_at.desc()).limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.fetchall()
        return [Message.model_validate(row) for row in rows]

    async def get_all_messages(self, user_id: int, limit: int | None = None) -> list[Message]:
        stmt = select(message_table).where(message_table.c.user_id == user_id).order_by(message_table.c.created_at.asc())

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        rows = result.fetchall()
        return [Message.model_validate(row) for row in rows]

    async def get_user_stats(self, user_id: int) -> UserStats:
        stmt = select(
            func.count(message_table.c.id).label("message_count"),
            func.min(message_table.c.created_at).label("first_message"),
            func.max(message_table.c.created_at).label("last_message"),
        ).where(message_table.c.user_id == user_id)

        result = await self.session.execute(stmt)
        row = result.one()

        return UserStats.model_validate(row)

    async def delete_messages(self, user_id: int) -> int:
        stmt = delete(message_table).where(message_table.c.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore

    async def delete_last_message(self, user_id: int) -> None:
        messages = await self.get_newest_messages(user_id, limit=1)
        if not messages or len(messages) == 0:
            return

        stmt = delete(message_table).where(message_table.c.user_id == user_id).where(message_table.c.id == messages[0].id)
        await self.session.execute(stmt)
        return
