from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, exists, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.exceptions import UserBanAlreadyExistsError, UserBanNotFoundError
from songbird.models.management.user_ban import UserBan, user_ban_table

STMT_CREATE_BAN = (
    insert(user_ban_table)
    .values(
        user_id=bindparam("b_user_id"),
        reason=bindparam("b_reason"),
    )
    .returning(user_ban_table)
)

STMT_GET_BAN = select(user_ban_table).where(user_ban_table.c.user_id == bindparam("b_user_id"))

STMT_IS_BANNED = select(exists().where(user_ban_table.c.user_id == bindparam("b_user_id")))

STMT_DELETE_BAN = (
    delete(user_ban_table).where(user_ban_table.c.user_id == bindparam("b_user_id")).returning(user_ban_table.c.user_id)
)

STMT_LIST_BANS = select(user_ban_table).order_by(user_ban_table.c.created_at.desc())


@dataclass
class UserBanRepository:
    session: AsyncSession

    async def create_ban(self, user_id: int, reason: str | None = None) -> UserBan:
        params: dict[str, Any] = {
            "b_user_id": user_id,
            "b_reason": reason,
        }

        try:
            result = await self.session.execute(STMT_CREATE_BAN, params)
        except IntegrityError as e:
            raise UserBanAlreadyExistsError(data={"user_id": user_id}) from e

        return UserBan.model_validate(result.mappings().one())

    async def get_ban(self, user_id: int) -> UserBan:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_GET_BAN, params)
        row = result.mappings().one_or_none()

        if row is None:
            raise UserBanNotFoundError(data={"user_id": user_id})

        return UserBan.model_validate(row)

    async def is_banned(self, user_id: int) -> bool:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_IS_BANNED, params)
        return result.scalar_one()

    async def delete_ban(self, user_id: int) -> None:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_DELETE_BAN, params)
        if result.mappings().one_or_none() is None:
            raise UserBanNotFoundError(data={"user_id": user_id})

    async def list_bans(self) -> list[UserBan]:
        result = await self.session.execute(STMT_LIST_BANS)
        return [UserBan.model_validate(row) for row in result.mappings()]
