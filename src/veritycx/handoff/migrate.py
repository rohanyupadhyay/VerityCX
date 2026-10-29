"""Install independent checksummed Chatwoot migrations without changing core migrations."""

from hashlib import sha256
from pathlib import Path

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row

from veritycx.persistence.migrate import MigrationError, verify_schema

MIGRATIONS = (
    Path(__file__).with_name("001_chatwoot.sql"),
    Path(__file__).with_name("002_origin_scope.sql"),
)
MIGRATION_LOCK = 724063813


def migration_ledger() -> list[dict[str, object]]:
    """Hash each exact separately versioned integration migration."""
    return [
        {"version": version, "checksum": sha256(path.read_bytes()).hexdigest()}
        for version, path in enumerate(MIGRATIONS, 1)
    ]


async def verify_chatwoot_schema(conn: AsyncConnection[dict[str, object]]) -> None:
    """Reject unavailable or altered integration state without runtime DDL."""
    cursor = await conn.execute(
        "SELECT version,checksum FROM support_chatwoot.migrations ORDER BY version"
    )
    if await cursor.fetchall() != migration_ledger():
        raise MigrationError("chatwoot_schema_mismatch")


async def migrate_chatwoot(admin_dsn: str, runtime_role: str) -> None:
    """Apply only unapplied reviewed migrations and grant runtime DML without schema authority."""
    if runtime_role not in {"veritycx_support", "veritycx_support_test"}:
        raise MigrationError("invalid_runtime_role")
    async with await AsyncConnection.connect(
        admin_dsn, autocommit=True, row_factory=dict_row
    ) as conn:
        await verify_schema(conn)
        await conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            async with conn.transaction():
                await conn.execute("CREATE SCHEMA IF NOT EXISTS support_chatwoot")
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS support_chatwoot.migrations "
                    "(version integer PRIMARY KEY, checksum text NOT NULL)"
                )
                cursor = await conn.execute(
                    "SELECT version,checksum FROM support_chatwoot.migrations ORDER BY version"
                )
                rows = await cursor.fetchall()
                expected = migration_ledger()
                if rows != expected[: len(rows)]:
                    raise MigrationError("chatwoot_schema_mismatch")
                for entry, path in zip(expected[len(rows) :], MIGRATIONS[len(rows) :], strict=True):
                    await conn.execute(path.read_text(encoding="utf-8"))
                    await conn.execute(
                        "INSERT INTO support_chatwoot.migrations VALUES (%s,%s)",
                        (entry["version"], entry["checksum"]),
                    )
                await conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA support_chatwoot TO {}").format(
                        sql.Identifier(runtime_role)
                    )
                )
                await conn.execute(
                    sql.SQL(
                        "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN "
                        "SCHEMA support_chatwoot TO {}"
                    ).format(sql.Identifier(runtime_role))
                )
                await conn.execute(
                    sql.SQL(
                        "REVOKE INSERT,UPDATE,DELETE ON support_chatwoot.migrations FROM {}"
                    ).format(sql.Identifier(runtime_role))
                )
            await verify_chatwoot_schema(conn)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
