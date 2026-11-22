from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.models.management.audit_log import AuditLogAction, audit_log_table
from songbird.repositories.management.audit_log import AuditLogRepository
from songbird.services.audit_log import AuditLogService

pytestmark = pytest.mark.db


async def test_log_persists_every_field(session: AsyncSession) -> None:
    service = AuditLogService(AuditLogRepository(session))

    await service.log(
        AuditLogAction.BLACKWALL_BAN,
        actor_id=1,
        target_id=2,
        guild_id=3,
        channel_id=4,
        metadata={"punishment": "ban"},
    )
    await session.commit()

    row = (await session.execute(select(audit_log_table))).mappings().one()
    assert row["action"] == AuditLogAction.BLACKWALL_BAN.value
    assert row["actor_id"] == 1
    assert row["target_id"] == 2
    assert row["guild_id"] == 3
    assert row["channel_id"] == 4
    assert row["metadata"] == {"punishment": "ban"}


async def test_log_defaults_metadata_to_empty_dict(session: AsyncSession) -> None:
    service = AuditLogService(AuditLogRepository(session))

    await service.log(AuditLogAction.BLACKWALL_BAN)
    await session.commit()

    row = (await session.execute(select(audit_log_table))).mappings().one()
    assert row["metadata"] == {}
    assert row["actor_id"] is None


async def test_repository_failure_propagates() -> None:
    class _Broken:
        async def create(self, _log: object) -> None:
            raise RuntimeError("database is down")

    service = AuditLogService(cast(AuditLogRepository, _Broken()))

    with pytest.raises(RuntimeError, match="database is down"):
        await service.log(AuditLogAction.BLACKWALL_BAN)
