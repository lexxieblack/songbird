import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DB_ROOT = Path(__file__).resolve().parents[2] / "database"
MIGRATION_DIRS = ("chat", "feedback", "management")
TABLE_NAMES = (
    "chat.message",
    "chat.guild_message",
    "chat.user_info",
    "feedback.thread",
    "management.user_ban",
    "management.guild_ban",
    "management.blackwall",
    "management.audit_log",
)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    if override := os.environ.get("TEST_DATABASE_URL"):
        yield override
        return

    from testcontainers.community.postgres import PostgresContainer

    try:
        # Construction already contacts the daemon, so it belongs inside the guard.
        container = PostgresContainer("postgres:16-alpine", driver="psycopg")
        container.start()
    except Exception as exc:  # noqa: BLE001 - Docker absence is environmental
        pytest.skip(f"Docker unavailable for the Postgres harness (set TEST_DATABASE_URL to use an existing database): {exc}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


async def apply_migrations(url: str) -> None:
    raw = url.replace("postgresql+psycopg", "postgresql")
    async with await psycopg.AsyncConnection.connect(raw, autocommit=True) as conn:
        # Migrations are not idempotent, so replay only works on fresh schemas.
        # Destructive: TEST_DATABASE_URL must point at a throwaway database.
        await conn.execute("DROP SCHEMA IF EXISTS chat, feedback, management CASCADE")
        for directory in MIGRATION_DIRS:
            for migration in sorted((DB_ROOT / directory).glob("*.sql")):
                await conn.execute(migration.read_text())  # pyright: ignore[reportArgumentType, reportCallIssue]


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    await apply_migrations(postgres_url)
    eng = create_async_engine(postgres_url)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(engine, expire_on_commit=False, autoflush=False)() as s:
        try:
            yield s
        finally:
            await s.rollback()
