from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, PrimaryKeyConstraint, Table, func

from songbird.models._base_db_model import BaseDBModel
from songbird.models.feedback.base import metadata

thread_table = Table(
    "thread",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("thread_id", BigInteger, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=func.now()),
    PrimaryKeyConstraint("user_id", "thread_id"),
)


class Thread(BaseDBModel):
    user_id: int
    thread_id: int
    created_at: datetime
