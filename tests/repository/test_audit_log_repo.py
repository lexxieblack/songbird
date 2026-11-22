import uuid
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.audit_log import AuditLogAction, CreateAuditLog
from songbird.repositories.management.audit_log import AuditLogRepository

pytestmark = pytest.mark.db


async def test_create_returns_all_fields(session: AsyncSession) -> None:
    repo = AuditLogRepository(session)
    created = await repo.create(
        CreateAuditLog(
            action=AuditLogAction.BLACKWALL_BAN,
            actor_id=1,
            target_id=2,
            guild_id=3,
            channel_id=4,
            metadata={"nested": {"ids": [1, 2]}},
        )
    )
    await session.commit()

    assert isinstance(created.id, UUID)
    assert created.action is AuditLogAction.BLACKWALL_BAN
    assert (created.actor_id, created.target_id, created.guild_id, created.channel_id) == (1, 2, 3, 4)
    assert created.metadata == {"nested": {"ids": [1, 2]}}
    assert created.created_at.tzinfo is not None


async def test_create_with_optional_fields_omitted(session: AsyncSession) -> None:
    repo = AuditLogRepository(session)
    created = await repo.create(
        CreateAuditLog(action=AuditLogAction.BLACKWALL_BAN, actor_id=None, target_id=None, guild_id=None, channel_id=None)
    )
    await session.commit()

    assert created.actor_id is None
    assert created.target_id is None
    assert created.guild_id is None
    assert created.channel_id is None
    assert created.metadata == {}


async def test_duplicate_id_propagates_integrity_error(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_id = uuid.uuid4()
    monkeypatch.setattr("songbird.repositories.management.audit_log.make_id", lambda: fixed_id)
    repo = AuditLogRepository(session)
    await repo.create(
        CreateAuditLog(action=AuditLogAction.BLACKWALL_BAN, actor_id=None, target_id=None, guild_id=None, channel_id=None)
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repo.create(
            CreateAuditLog(action=AuditLogAction.BLACKWALL_BAN, actor_id=None, target_id=None, guild_id=None, channel_id=None)
        )
    await session.rollback()
