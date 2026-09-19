"""Prove administrative migration checks and runtime privilege separation on PostgreSQL."""

import os

import psycopg
import pytest
from psycopg.rows import dict_row

from tests.support.harness import require_test_database
from veritycx.persistence.migrate import MigrationError, migrate, verify_schema
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_migration_and_runtime_privileges(test_database_url: str) -> None:
    """Install once, repeat safely, and deny runtime DDL on application tables."""
    admin = require_test_database(os.environ.get("VERITYCX_TEST_MIGRATION_DATABASE_URL", ""))

    async def exercise() -> None:
        """Run migrations and inspect the actual connected server and grants."""
        await migrate(admin, "veritycx_support_test")
        await migrate(admin, "veritycx_support_test")
        async with await psycopg.AsyncConnection.connect(
            test_database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            await verify_schema(conn)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute("CREATE TABLE support_app.forbidden_test_table (id int)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute("UPDATE support_meta.migrations SET checksum = 'tampered'")
        async with await psycopg.AsyncConnection.connect(
            admin, autocommit=True, row_factory=dict_row
        ) as conn:
            with pytest.raises(MigrationError, match="schema_mismatch"):
                async with conn.transaction():
                    await conn.execute("UPDATE support_meta.migrations SET checksum = 'tampered'")
                    await verify_schema(conn)
            await verify_schema(conn)
            with pytest.raises(RuntimeError):
                async with conn.transaction():
                    await conn.execute("CREATE TABLE support_app.rollback_probe (id int)")
                    raise RuntimeError("rollback")
            cursor = await conn.execute(
                "SELECT to_regclass('support_app.rollback_probe') AS relation"
            )
            row = await cursor.fetchone()
            assert row is not None and row["relation"] is None

    run_async(exercise())
