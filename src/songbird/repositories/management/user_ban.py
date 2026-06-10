from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import UserBanAlreadyExistsError, UserBanNotFoundError
from songbird.models.management.user_ban import UserBan, user_ban_table


@dataclass
class UserBanRepository:
    session: AsyncSession

    async def create_ban(self, user_id: int, reason: str | None = None) -> UserBan:
        stmt = (
            insert(user_ban_table)
            .values(
                user_id=user_id,
                reason=reason,
            )
            .returning(user_ban_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise UserBanAlreadyExistsError(data={"user_id": user_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create user ban")

        return UserBan.model_validate(row)

    async def get_ban(self, user_id: int) -> UserBan:
        result = await self.session.execute(select(user_ban_table).where(user_ban_table.c.user_id == user_id))
        row = result.one_or_none()

        if row is None:
            raise UserBanNotFoundError(data={"user_id": user_id})

        return UserBan.model_validate(row)

    async def is_banned(self, user_id: int) -> bool:
        result = await self.session.execute(select(user_ban_table).where(user_ban_table.c.user_id == user_id))
        return result.one_or_none() is not None

    async def delete_ban(self, user_id: int) -> None:
        stmt = delete(user_ban_table).where(user_ban_table.c.user_id == user_id)
        result = await self.session.execute(stmt)

        if result.rowcount == 0:  # type: ignore
            raise UserBanNotFoundError(data={"user_id": user_id})

    async def list_bans(self) -> list[UserBan]:
        result = await self.session.execute(select(user_ban_table).order_by(user_ban_table.c.created_at.desc()))
        return [UserBan.model_validate(row) for row in result.fetchall()]
