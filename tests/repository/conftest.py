from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.database import TABLE_NAMES


@pytest.fixture(autouse=True)
async def _truncate(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text(f"truncate {', '.join(TABLE_NAMES)}"))
