from dataclasses import dataclass

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.feedback.exceptions import ThreadAlreadyExistsError, ThreadNotFoundError
from songbird.models.feedback.thread import Thread, thread_table


@dataclass
class ThreadRepository:
    session: AsyncSession

    async def create_thread(self, user_id: int, thread_id: int) -> Thread:
        stmt = (
            insert(thread_table)
            .values(
                user_id=user_id,
                thread_id=thread_id,
            )
            .returning(thread_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise ThreadAlreadyExistsError(data={"user_id": user_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create thread")

        return Thread.model_validate(row)

    async def get_thread(self, user_id: int) -> Thread:
        result = await self.session.execute(select(thread_table).where(thread_table.c.user_id == user_id))
        row = result.one_or_none()

        if row is None:
            raise ThreadNotFoundError(data={"user_id": user_id})

        return Thread.model_validate(row)
