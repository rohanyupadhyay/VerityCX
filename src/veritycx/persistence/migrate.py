"""Apply checksummed administrative migrations; runtime checks never execute DDL."""

from hashlib import sha256
from pathlib import Path

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row

MIGRATION = Path(__file__).parent / "migrations" / "001_support.sql"
MIGRATION_LOCK = 724063812


class MigrationError(ValueError):
    """Expose safe version/checksum mismatch categories without connection details."""


def migration_checksum() -> str:
    """Hash exact migration bytes to detect edits after administrative application."""
    return sha256(MIGRATION.read_bytes()).hexdigest()


async def verify_version(conn: AsyncConnection[dict[str, object]]) -> None:
    """Require the reviewed native server version before schema access."""
    cursor = await conn.execute("SELECT current_setting('server_version_num') AS version")
    row = await cursor.fetchone()
    if row is None or row.get("version") != "180006":
        raise MigrationError("unsupported_database_version")


async def verify_schema(conn: AsyncConnection[dict[str, object]]) -> None:
    """Check the exact ledger and pinned saver version without changing storage."""
    await verify_version(conn)
    cursor = await conn.execute(
        "SELECT version, checksum FROM support_meta.migrations ORDER BY version"
    )
    rows = await cursor.fetchall()
    if rows != [{"version": 1, "checksum": migration_checksum()}]:
        raise MigrationError("schema_mismatch")
    cursor = await conn.execute(
        "SELECT max(v) AS version FROM support_checkpoints.checkpoint_migrations"
    )
    row = await cursor.fetchone()
    if row is None or row.get("version") != len(AsyncPostgresSaver.MIGRATIONS) - 1:
        raise MigrationError("schema_mismatch")


async def migrate(admin_dsn: str, runtime_role: str) -> None:
    """Install the application and pinned saver schemas; never drop existing user data."""
    if runtime_role not in {"veritycx_support", "veritycx_support_test"}:
        raise MigrationError("invalid_runtime_role")
    async with await AsyncConnection.connect(
        admin_dsn, autocommit=True, row_factory=dict_row
    ) as conn:
        await verify_version(conn)
        await conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            async with conn.transaction():
                await conn.execute("CREATE SCHEMA IF NOT EXISTS support_meta")
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS support_meta.migrations "
                    "(version integer PRIMARY KEY, checksum text NOT NULL)"
                )
                cursor = await conn.execute("SELECT version, checksum FROM support_meta.migrations")
                rows = await cursor.fetchall()
                if rows and rows != [{"version": 1, "checksum": migration_checksum()}]:
                    raise MigrationError("schema_mismatch")
                await conn.execute("CREATE SCHEMA IF NOT EXISTS support_app")
                await conn.execute("CREATE SCHEMA IF NOT EXISTS support_checkpoints")
                if not rows:
                    await conn.execute(MIGRATION.read_text(encoding="utf-8"))
                    await conn.execute(
                        "INSERT INTO support_meta.migrations VALUES (1,%s)", (migration_checksum(),)
                    )
            # Saver setup contains concurrent index migrations and needs autocommit.
            # Keep the session advisory lock across both administrative phases.
            await conn.execute("SET search_path TO support_checkpoints, pg_catalog")
            await AsyncPostgresSaver(conn).setup()
            async with conn.transaction():
                await conn.execute(
                    sql.SQL(
                        "GRANT USAGE ON SCHEMA support_app, support_checkpoints, support_meta TO {}"
                    ).format(sql.Identifier(runtime_role))
                )
                await conn.execute(
                    sql.SQL(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN "
                        "SCHEMA support_app, support_checkpoints TO {}"
                    ).format(sql.Identifier(runtime_role))
                )
                await conn.execute(
                    sql.SQL(
                        "REVOKE INSERT, UPDATE, DELETE ON "
                        "support_checkpoints.checkpoint_migrations FROM {}"
                    ).format(sql.Identifier(runtime_role))
                )
                await conn.execute(
                    sql.SQL("GRANT SELECT ON support_meta.migrations TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )
            await verify_schema(conn)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
