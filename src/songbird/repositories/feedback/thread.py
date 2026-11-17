from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.feedback.exceptions import ThreadAlreadyExistsError, ThreadNotFoundError
from songbird.models.feedback.thread import Thread, thread_table

STMT_CREATE_THREAD = (
    insert(thread_table)
    .values(
        user_id=bindparam("b_user_id"),
        thread_id=bindparam("b_thread_id"),
    )
    .returning(thread_table)
)

STMT_GET_THREAD = select(thread_table).where(thread_table.c.user_id == bindparam("b_user_id"))


@dataclass
class ThreadRepository:
    session: AsyncSession

    async def create_thread(self, user_id: int, thread_id: int) -> Thread:
        params: dict[str, Any] = {
            "b_user_id": user_id,
            "b_thread_id": thread_id,
        }

        try:
            result = await self.session.execute(STMT_CREATE_THREAD, params)
        except IntegrityError as e:
            raise ThreadAlreadyExistsError(data={"user_id": user_id}) from e

        return Thread.model_validate(result.mappings().one())

    async def get_thread(self, user_id: int) -> Thread:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_GET_THREAD, params)
        row = result.mappings().one_or_none()

        if row is None:
            raise ThreadNotFoundError(data={"user_id": user_id})

        return Thread.model_validate(row)
