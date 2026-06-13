from enum import Enum

from sqlalchemy import Enum as PGEnum
from sqlalchemy import MetaData

metadata = MetaData(schema="chat")


class MessageRole(Enum):
    USER = "user"
    MODEL = "model"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value


MessageRoleEnum = PGEnum(
    *[role.value for role in MessageRole],
    name="message_role",
    schema="chat",
    create_constraint=True,
    validate_strings=True,
)
