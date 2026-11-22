import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.database import TABLE_NAMES

pytestmark = pytest.mark.db

SCHEMAS = {"chat", "feedback", "management"}
ENUMS = {
    "chat.message_role",
    "management.log_action",
    "management.blackwall_punishment",
}


async def test_schemas_exist(session: AsyncSession) -> None:
    rows = await session.execute(text("select schema_name from information_schema.schemata"))
    assert set(rows.scalars()) >= SCHEMAS


async def test_tables_exist(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "select table_schema || '.' || table_name from information_schema.tables "
            "where table_schema in ('chat', 'feedback', 'management')"
        )
    )
    assert set(rows.scalars()) == set(TABLE_NAMES)


async def test_enums_exist(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "select n.nspname || '.' || t.typname from pg_type t "
            "join pg_namespace n on n.oid = t.typnamespace "
            "where t.typtype = 'e' and n.nspname in ('chat', 'feedback', 'management')"
        )
    )
    assert set(rows.scalars()) >= ENUMS


async def test_blackwall_punishment_column(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text(
                "select data_type, column_default from information_schema.columns "
                "where table_schema = 'management' and table_name = 'blackwall' and column_name = 'punishment'"
            )
        )
    ).one_or_none()
    assert row is not None
    assert row.data_type in {"character varying", "USER-DEFINED"}
    assert row.column_default is not None
