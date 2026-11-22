from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from songbird.config import Settings
from songbird.services.container import ServiceContainer
from tests.support.database import TABLE_NAMES


@pytest.fixture(autouse=True)
async def _truncate(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    # Requesting `engine` eagerly would make every unit test need Docker, so only DB tests pay for it.
    engine = cast(AsyncEngine, request.getfixturevalue("engine")) if request.node.get_closest_marker("db") else None
    yield
    if engine is not None:
        async with engine.begin() as conn:
            await conn.execute(text(f"truncate {', '.join(TABLE_NAMES)}"))


@pytest.fixture
def db_container(engine: AsyncEngine, settings: Settings) -> ServiceContainer:
    """Only the DB-facing parts of the container; services under test touch nothing else."""
    return cast(
        ServiceContainer,
        SimpleNamespace(
            engine=engine,
            session_factory=async_sessionmaker(engine, expire_on_commit=False, autoflush=False),
            settings=settings,
        ),
    )
