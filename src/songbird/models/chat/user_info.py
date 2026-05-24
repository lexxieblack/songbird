from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, PrimaryKeyConstraint, Table, Text, func

from songbird.models._base_db_model import BaseDBModel
from songbird.models.chat.base import metadata

user_info_table = Table(
    "user_info",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("user_info", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=func.now()),
    PrimaryKeyConstraint("user_id"),
)


class UserInfo(BaseDBModel):
    user_id: int
    user_info: str
    created_at: datetime
    updated_at: datetime
