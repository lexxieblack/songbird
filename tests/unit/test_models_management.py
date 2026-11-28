from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import JSONB

from songbird.models.exception import SongbirdException
from songbird.models.management.audit_log import (
    AuditLog,
    AuditLogAction,
    AuditLogActionEnum,
    CreateAuditLog,
    audit_log_table,
)
from songbird.models.management.blackwall import (
    Blackwall,
    BlackwallPunishment,
    CreateBlackwall,
    PunishmentType,
    blackwall_table,
)
from songbird.models.management.exceptions import (
    BlackwallAlreadyExistsError,
    BlackwallNotFoundError,
    GuildBanAlreadyExistsError,
    GuildBanNotFoundError,
    UserBanAlreadyExistsError,
    UserBanNotFoundError,
)
from songbird.models.management.guild_ban import GuildBan, guild_ban_table
from songbird.models.management.user_ban import UserBan, user_ban_table

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_audit_log_action_string_and_repr() -> None:
    action = AuditLogAction.BLACKWALL_BAN

    assert action.value == "blackwall_ban"
    assert str(action) == "blackwall_ban"
    assert repr(action) == "blackwall_ban"


def test_audit_log_action_enum_metadata() -> None:
    assert AuditLogActionEnum.enums == ["blackwall_log", "blackwall_warn", "blackwall_kick", "blackwall_ban"]
    assert AuditLogActionEnum.name == "log_action"
    assert AuditLogActionEnum.schema == "management"  # pyright: ignore[reportUnknownMemberType]


def test_management_tables_live_in_the_management_schema() -> None:
    for table in (audit_log_table, blackwall_table, guild_ban_table, user_ban_table):
        assert table.metadata.schema == "management"
        assert table.fullname == f"management.{table.name}"


def test_audit_log_table_columns_and_server_default() -> None:
    assert set(audit_log_table.columns.keys()) == {
        "id",
        "action",
        "actor_id",
        "target_id",
        "guild_id",
        "channel_id",
        "metadata",
        "created_at",
    }
    assert list(audit_log_table.primary_key.columns.keys()) == ["id"]
    assert audit_log_table.c.action.nullable is False
    assert audit_log_table.c.actor_id.nullable is True
    assert audit_log_table.c.metadata.nullable is False
    assert isinstance(audit_log_table.c.metadata.type, JSONB)

    server_default = audit_log_table.c.metadata.server_default
    assert server_default is not None
    assert "{}" in str(cast(Any, server_default).arg)


def test_create_audit_log_defaults_metadata_per_instance() -> None:
    values: dict[str, int | AuditLogAction] = {
        "action": AuditLogAction.BLACKWALL_BAN,
        "actor_id": 1,
        "target_id": 2,
        "guild_id": 3,
        "channel_id": 4,
    }

    first = CreateAuditLog(**values)  # type: ignore[arg-type]
    second = CreateAuditLog(**values)  # type: ignore[arg-type]

    assert first.metadata == {}
    assert first.metadata is not second.metadata


def test_create_audit_log_requires_actor_target_guild_and_channel() -> None:
    with pytest.raises(ValidationError):
        CreateAuditLog(action="blackwall_ban")  # type: ignore[call-arg, arg-type]


def test_create_audit_log_is_frozen() -> None:
    audit_log = CreateAuditLog(action=AuditLogAction.BLACKWALL_BAN, actor_id=1, target_id=2, guild_id=3, channel_id=4)

    with pytest.raises(ValidationError):
        audit_log.action = AuditLogAction.BLACKWALL_BAN


def test_audit_log_reads_attributes() -> None:
    audit_log = AuditLog.model_validate(
        SimpleNamespace(
            id=uuid4(),
            action="blackwall_ban",
            actor_id=None,
            target_id=None,
            guild_id=None,
            channel_id=None,
            metadata={"reason": "spam"},
            created_at=NOW,
        )
    )

    assert audit_log.action is AuditLogAction.BLACKWALL_BAN
    assert audit_log.metadata == {"reason": "spam"}


@pytest.mark.parametrize(
    ("punishment", "value"),
    [
        (BlackwallPunishment.LOG, "log"),
        (BlackwallPunishment.WARN, "warn"),
        (BlackwallPunishment.KICK, "kick"),
        (BlackwallPunishment.BAN, "ban"),
    ],
)
def test_blackwall_punishment_string_and_repr(punishment: BlackwallPunishment, value: str) -> None:
    assert punishment.value == value
    assert str(punishment) == value
    assert repr(punishment) == value


def test_punishment_type_enum_metadata() -> None:
    assert PunishmentType.enums == ["log", "warn", "kick", "ban"]
    assert PunishmentType.name == "blackwall_punishment"
    assert PunishmentType.schema == "management"  # pyright: ignore[reportUnknownMemberType]


def test_blackwall_table_column_defaults() -> None:
    assert list(blackwall_table.primary_key.columns.keys()) == ["guild_id"]
    assert blackwall_table.c.whitelisted_roles.nullable is False
    assert blackwall_table.c.banned_count.nullable is False
    assert blackwall_table.c.punishment.nullable is False

    roles_default = blackwall_table.c.whitelisted_roles.default
    punishment_default = blackwall_table.c.punishment.default
    assert roles_default is not None
    assert punishment_default is not None
    assert cast(Any, roles_default).arg == []
    assert cast(Any, punishment_default).arg == "ban"


def test_create_blackwall_defaults_punishment_and_roles_per_instance() -> None:
    first = CreateBlackwall(guild_id=1, channel_id=None)
    second = CreateBlackwall(guild_id=2, channel_id=None)

    assert first.punishment is BlackwallPunishment.BAN
    assert first.log_channel_id is None
    assert first.whitelisted_roles == []
    assert first.whitelisted_roles is not second.whitelisted_roles


def test_create_blackwall_requires_channel_id() -> None:
    with pytest.raises(ValidationError):
        CreateBlackwall(guild_id=1)  # type: ignore[call-arg]


def test_create_blackwall_is_frozen() -> None:
    config = CreateBlackwall(guild_id=1, channel_id=None)

    with pytest.raises(ValidationError):
        config.punishment = BlackwallPunishment.KICK


def test_blackwall_reads_attributes_and_coerces_punishment() -> None:
    config = Blackwall.model_validate(
        SimpleNamespace(
            guild_id=1,
            channel_id=None,
            log_channel_id=2,
            whitelisted_roles=[3],
            punishment="kick",
            banned_count=4,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    assert config.punishment is BlackwallPunishment.KICK
    assert config.whitelisted_roles == [3]
    assert config.banned_count == 4


def test_user_ban_model_and_table() -> None:
    ban = UserBan(user_id=1, reason=None, created_at=NOW)

    assert ban.reason is None
    assert user_ban_table.fullname == "management.user_ban"
    assert list(user_ban_table.primary_key.columns.keys()) == ["user_id"]
    assert user_ban_table.c.reason.nullable is True
    assert user_ban_table.c.created_at.nullable is False


def test_guild_ban_model_and_table() -> None:
    ban = GuildBan(guild_id=1, reason="spam", created_at=NOW)

    assert ban.reason == "spam"
    assert guild_ban_table.fullname == "management.guild_ban"
    assert list(guild_ban_table.primary_key.columns.keys()) == ["guild_id"]
    assert guild_ban_table.c.reason.nullable is True
    assert guild_ban_table.c.created_at.nullable is False


@pytest.mark.parametrize(
    ("error_type", "default_message"),
    [
        (UserBanAlreadyExistsError, "User ban already exists"),
        (UserBanNotFoundError, "User ban not found"),
        (GuildBanAlreadyExistsError, "Guild ban already exists"),
        (GuildBanNotFoundError, "Guild ban not found"),
        (BlackwallAlreadyExistsError, "Blackwall config already exists for this guild"),
        (BlackwallNotFoundError, "Blackwall config not found for this guild"),
    ],
)
def test_management_exceptions_have_default_messages(error_type: Callable[[], SongbirdException], default_message: str) -> None:
    error = error_type()

    assert str(error) == default_message
    assert error.data == {}


def test_management_exceptions_accept_a_custom_message_and_data() -> None:
    error = UserBanNotFoundError("missing ban", {"user_id": 1})

    assert str(error) == "missing ban"
    assert error.data == {"user_id": 1}
