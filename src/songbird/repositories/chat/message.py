from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.message import Message, UserStats, message_table
from songbird.utils.id_factory import make_id

STMT_CREATE_MESSAGE = (
    insert(message_table)
    .values(
        id=bindparam("b_id"),
        user_id=bindparam("b_user_id"),
        role=bindparam("b_role"),
        content=bindparam("b_content"),
    )
    .returning(message_table)
)

STMT_GET_NEWEST_MESSAGES = (
    select(message_table)
    .where(message_table.c.user_id == bindparam("b_user_id"))
    .order_by(message_table.c.created_at.desc())
    .limit(bindparam("b_limit"))
)

STMT_GET_ALL_MESSAGES = (
    select(message_table).where(message_table.c.user_id == bindparam("b_user_id")).order_by(message_table.c.created_at.asc())
)

STMT_GET_USER_STATS = select(
    func.count(message_table.c.id).label("message_count"),
    func.min(message_table.c.created_at).label("first_message"),
    func.max(message_table.c.created_at).label("last_message"),
).where(message_table.c.user_id == bindparam("b_user_id"))

STMT_GET_NEWEST_MESSAGE_ID = (
    select(message_table.c.id)
    .where(message_table.c.user_id == bindparam("b_user_id"))
    .order_by(message_table.c.created_at.desc())
    .limit(1)
)

STMT_DELETE_MESSAGE = delete(message_table).where(message_table.c.id == bindparam("b_id"))

STMT_DELETE_MESSAGES = delete(message_table).where(message_table.c.user_id == bindparam("b_user_id"))


@dataclass
class MessageRepository:
    session: AsyncSession

    async def create_message(self, user_id: int, role: MessageRole, content: str) -> Message:
        params: dict[str, Any] = {
            "b_id": make_id(),
            "b_user_id": user_id,
            "b_role": role.value,
            "b_content": content,
        }

        try:
            result = await self.session.execute(STMT_CREATE_MESSAGE, params)
        except IntegrityError as e:
            raise MessageAlreadyExistsError(data={"user_id": user_id}) from e

        return Message.model_validate(result.mappings().one())

    async def get_newest_messages(self, user_id: int, limit: int = 100) -> list[Message]:
        params: dict[str, Any] = {
            "b_user_id": user_id,
            "b_limit": limit,
        }

        result = await self.session.execute(STMT_GET_NEWEST_MESSAGES, params)
        return [Message.model_validate(row) for row in result.mappings()]

    async def get_all_messages(self, user_id: int, limit: int | None = None) -> list[Message]:
        params: dict[str, Any] = {"b_user_id": user_id}

        stmt = STMT_GET_ALL_MESSAGES
        if limit is not None:
            stmt = stmt.limit(bindparam("b_limit"))
            params["b_limit"] = limit

        result = await self.session.execute(stmt, params)
        return [Message.model_validate(row) for row in result.mappings()]

    async def get_user_stats(self, user_id: int) -> UserStats:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_GET_USER_STATS, params)
        return UserStats.model_validate(result.mappings().one())

    async def delete_messages(self, user_id: int) -> int:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_DELETE_MESSAGES, params)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def delete_last_message(self, user_id: int) -> None:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_GET_NEWEST_MESSAGE_ID, params)
        message_id = result.scalar_one_or_none()
        if message_id is None:
            return

        await self.session.execute(STMT_DELETE_MESSAGE, {"b_id": message_id})
