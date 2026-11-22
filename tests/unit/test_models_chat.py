from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import BigInteger, Text

from songbird.models.chat.base import MessageRole, MessageRoleEnum
from songbird.models.chat.exceptions import MessageAlreadyExistsError, UserInfoAlreadyExistsError, UserInfoNotFoundError
from songbird.models.chat.guild_message import GuildMessage, guild_message_table
from songbird.models.chat.message import Message, UserStats, message_table
from songbird.models.chat.user_info import UserInfo, user_info_table
from songbird.models.exception import SongbirdException

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.mark.parametrize(("role", "value"), [(MessageRole.USER, "user"), (MessageRole.MODEL, "model")])
def test_message_role_string_and_repr(role: MessageRole, value: str) -> None:
    assert str(role) == value
    assert repr(role) == value
    assert role.value == value


def test_message_role_enum_metadata() -> None:
    assert MessageRoleEnum.enums == ["user", "model"]
    assert MessageRoleEnum.name == "message_role"
    assert MessageRoleEnum.schema == "chat"  # pyright: ignore[reportUnknownMemberType]


def test_chat_tables_live_in_the_chat_schema() -> None:
    assert message_table.metadata.schema == "chat"
    assert message_table.fullname == "chat.message"
    assert guild_message_table.fullname == "chat.guild_message"
    assert user_info_table.fullname == "chat.user_info"


def test_message_table_columns_and_constraints() -> None:
    assert set(message_table.columns.keys()) == {"id", "user_id", "role", "content", "created_at"}
    assert list(message_table.primary_key.columns.keys()) == ["id"]
    assert message_table.c.id.nullable is False
    assert message_table.c.user_id.nullable is False
    assert message_table.c.role.nullable is False
    assert message_table.c.content.nullable is False
    assert message_table.c.created_at.nullable is False
    assert message_table.c.created_at.default is not None
    assert isinstance(message_table.c.user_id.type, BigInteger)
    assert isinstance(message_table.c.content.type, Text)


def test_guild_message_table_columns_and_constraints() -> None:
    assert set(guild_message_table.columns.keys()) == {"id", "guild_id", "role", "content", "created_at"}
    assert list(guild_message_table.primary_key.columns.keys()) == ["id"]
    assert guild_message_table.c.guild_id.nullable is False
    assert guild_message_table.c.role.nullable is False
    assert guild_message_table.c.created_at.nullable is False


def test_user_info_table_allows_null_user_info() -> None:
    assert set(user_info_table.columns.keys()) == {"user_id", "user_info", "created_at", "updated_at"}
    assert list(user_info_table.primary_key.columns.keys()) == ["user_id"]
    assert user_info_table.c.user_info.nullable is True
    assert user_info_table.c.created_at.nullable is False
    assert user_info_table.c.updated_at.nullable is False


def test_message_accepts_a_role_string_and_reads_attributes() -> None:
    message = Message.model_validate(SimpleNamespace(id=uuid4(), user_id=1, role="user", content="hi", created_at=NOW))

    assert message.role is MessageRole.USER
    assert message.content == "hi"


@pytest.mark.parametrize("missing", ["id", "user_id", "role", "content", "created_at"])
def test_message_requires_every_field(missing: str) -> None:
    values: dict[str, object] = {"id": uuid4(), "user_id": 1, "role": "user", "content": "hi", "created_at": NOW}
    values.pop(missing)

    with pytest.raises(ValidationError):
        Message.model_validate(values)


def test_guild_message_reads_attributes() -> None:
    message = GuildMessage.model_validate(
        SimpleNamespace(id=uuid4(), guild_id=2, role=MessageRole.MODEL, content="hi", created_at=NOW)
    )

    assert message.guild_id == 2
    assert message.role is MessageRole.MODEL


def test_user_info_allows_a_null_info_value() -> None:
    info = UserInfo(user_id=1, user_info=None, created_at=NOW, updated_at=NOW)

    assert info.user_info is None


def test_user_stats_reads_attributes() -> None:
    stats = UserStats.model_validate(SimpleNamespace(user_id=1, message_count=3, first_message=NOW, last_message=NOW))

    assert stats.message_count == 3


@pytest.mark.parametrize(
    ("error_type", "default_message"),
    [
        (UserInfoAlreadyExistsError, "User info already exists"),
        (UserInfoNotFoundError, "User info not found"),
        (MessageAlreadyExistsError, "Message already exists"),
    ],
)
def test_chat_exceptions_have_default_messages(error_type: Callable[[], SongbirdException], default_message: str) -> None:
    error = error_type()

    assert str(error) == default_message
    assert error.data == {}


def test_chat_exceptions_accept_a_custom_message_and_data() -> None:
    error = MessageAlreadyExistsError("duplicate", {"message_id": 1})

    assert str(error) == "duplicate"
    assert error.data == {"message_id": 1}
