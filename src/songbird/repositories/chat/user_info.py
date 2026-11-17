from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.exceptions import UserInfoAlreadyExistsError, UserInfoNotFoundError
from songbird.models.chat.user_info import UserInfo, user_info_table

STMT_CREATE_USER_INFO = (
    insert(user_info_table)
    .values(
        user_id=bindparam("b_user_id"),
        user_info=bindparam("b_user_info"),
    )
    .returning(user_info_table)
)

STMT_GET_USER_INFO = select(user_info_table).where(user_info_table.c.user_id == bindparam("b_user_id"))

STMT_UPDATE_USER_INFO = (
    update(user_info_table)
    .where(user_info_table.c.user_id == bindparam("b_user_id"))
    .values(user_info=bindparam("b_user_info"))
    .returning(user_info_table)
)

STMT_DELETE_USER_INFO = delete(user_info_table).where(user_info_table.c.user_id == bindparam("b_user_id"))


@dataclass
class UserInfoRepository:
    session: AsyncSession

    async def create_user_info(self, user_id: int, user_info: str) -> UserInfo:
        params: dict[str, Any] = {
            "b_user_id": user_id,
            "b_user_info": user_info,
        }

        try:
            result = await self.session.execute(STMT_CREATE_USER_INFO, params)
        except IntegrityError as e:
            raise UserInfoAlreadyExistsError(data={"user_id": user_id}) from e

        return UserInfo.model_validate(result.mappings().one())

    async def get_user_info(self, user_id: int) -> UserInfo:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_GET_USER_INFO, params)
        row = result.mappings().one_or_none()

        if row is None:
            raise UserInfoNotFoundError(data={"user_id": user_id})

        return UserInfo.model_validate(row)

    async def update_user_info(self, user_id: int, user_info: str) -> UserInfo:
        params: dict[str, Any] = {
            "b_user_id": user_id,
            "b_user_info": user_info,
        }

        result = await self.session.execute(STMT_UPDATE_USER_INFO, params)
        row = result.mappings().one_or_none()

        if row is None:
            raise UserInfoNotFoundError(data={"user_id": user_id})

        return UserInfo.model_validate(row)

    async def delete_user_info(self, user_id: int) -> int:
        params: dict[str, Any] = {"b_user_id": user_id}

        result = await self.session.execute(STMT_DELETE_USER_INFO, params)
        return int(result.rowcount)  # type: ignore[attr-defined]
