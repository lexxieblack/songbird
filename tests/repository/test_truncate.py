"""Intentionally order-dependent: `test_row_is_gone` proves the autouse truncate fixture wiped the row
`test_writes_a_row` inserted, so it must run after it.
"""

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from songbird.models.management.guild_ban import guild_ban_table

pytestmark = pytest.mark.db


async def test_writes_a_row(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(insert(guild_ban_table).values(guild_id=999, reason="truncate-probe"))


async def test_row_is_gone(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        row = (await conn.execute(select(guild_ban_table).where(guild_ban_table.c.guild_id == 999))).one_or_none()
    assert row is None
