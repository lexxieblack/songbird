from dataclasses import dataclass

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.chat.exceptions import UserInfoAlreadyExistsError, UserInfoNotFoundError
from songbird.models.chat.user_info import UserInfo, user_info_table


@dataclass
class UserInfoRepository:
    session: AsyncSession

    async def create_user_info(self, user_id: int, user_info: str) -> UserInfo:
        stmt = (
            insert(user_info_table)
            .values(
                user_id=user_id,
                user_info=user_info,
            )
            .returning(user_info_table)
        )

        try:
            result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise UserInfoAlreadyExistsError(data={"user_id": user_id}) from e

        row = result.fetchone()
        if row is None:
            raise ValueError("Failed to create user info")

        return UserInfo.model_validate(row)

    async def get_user_info(self, user_id: int) -> UserInfo:
        result = await self.session.execute(select(user_info_table).where(user_info_table.c.user_id == user_id))
        row = result.one_or_none()

        if row is None:
            raise UserInfoNotFoundError(data={"user_id": user_id})

        return UserInfo.model_validate(row)

    async def update_user_info(self, user_id: int, user_info: str) -> UserInfo:
        stmt = (
            update(user_info_table)
            .where(user_info_table.c.user_id == user_id)
            .values(user_info=user_info)
            .returning(user_info_table)
        )

        result = await self.session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            raise UserInfoNotFoundError(data={"user_id": user_id})

        return UserInfo.model_validate(row)

    async def delete_user_info(self, user_id: int) -> int:
        stmt = delete(user_info_table).where(user_info_table.c.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore
