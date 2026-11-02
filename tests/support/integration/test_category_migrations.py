"""Prove real v2-prefix upgrades without resetting shared or application storage."""

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from tests.support.harness import OwnedProcesses
from tests.support.migration_harness import owned_migration_database
from veritycx.persistence import migrate as migrations
from veritycx.persistence.migrate import MigrationError, migrate, verify_schema
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_applied_migration_prefix_checksums_are_frozen() -> None:
    """Category support cannot rewrite either previously applied SQL migration."""
    assert [sha256(path.read_bytes()).hexdigest() for path in migrations.MIGRATIONS[:2]] == [
        "c7a8e1a89b2f171ef47b33ce0b44ee5ee4fef79938cfcb3cb923747251e5923e",
        "c38080887e5050e75f964392dee94de086e433f4de0b74bf394f546bad37cc04",
    ]


@pytest.mark.parametrize("legacy", [False, True])
def test_private_native_database_upgrades_without_rewriting_old_rows(
    tmp_path: Path, owned_processes: OwnedProcesses, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    """Fresh install and v2 upgrade retain old content, null provenance and grants."""
    inventory = migrations.MIGRATIONS
    assert len(inventory) == 3
    with owned_migration_database(tmp_path, owned_processes) as database:
        if legacy:
            with monkeypatch.context() as patch:
                patch.setattr(migrations, "MIGRATIONS", inventory[:2])
                run_async(migrate(database.admin_dsn, "veritycx_support_test"))
            parent, turn = uuid4(), uuid4()
            with psycopg.connect(database.admin_dsn, autocommit=True) as conn:
                conn.execute(
                    "INSERT INTO support_app.conversations "
                    "(id,owner_id,corpus_version,expires_at) "
                    "VALUES (%s,%s,'legacy',now()+interval '1 day')",
                    (parent, uuid4()),
                )
                conn.execute(
                    "INSERT INTO support_app.turns "
                    "(id,conversation_id,sequence,request_key,text,status) "
                    "VALUES (%s,%s,1,%s,'Retained fixture','completed')",
                    (turn, parent, uuid4()),
                )
                conn.execute(
                    "INSERT INTO support_app.query_rewrites "
                    "(turn_id,request_digest,model,prompt_version,status) "
                    "VALUES (%s,'legacy','fixture',1,'reserved')",
                    (turn,),
                )
                conn.execute(
                    "INSERT INTO support_app.audit "
                    "(id,conversation_id,turn_id,correlation_id,stage,outcome,route) "
                    "VALUES (%s,%s,%s,%s,'result','answer','knowledge')",
                    (uuid4(), parent, turn, uuid4()),
                )
        run_async(migrate(database.admin_dsn, "veritycx_support_test"))
        run_async(migrate(database.admin_dsn, "veritycx_support_test"))

        async def verify() -> None:
            """Inspect the actual installed ledger and immutable prefix checksums."""
            async with await psycopg.AsyncConnection.connect(
                database.runtime_dsn, autocommit=True, row_factory=dict_row
            ) as conn:
                await verify_schema(conn)
                rows = await (
                    await conn.execute(
                        "SELECT version,checksum FROM support_meta.migrations ORDER BY version"
                    )
                ).fetchall()
                assert rows == migrations.migration_inventory()
                assert [row["version"] for row in rows] == [1, 2, 3]
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    await conn.execute("CREATE TABLE support_app.forbidden_category_test (id int)")
                if legacy:
                    row = await (
                        await conn.execute(
                            "SELECT q.prompt_version,q.search_scope,q.category_keys,"
                            "a.prompt_version "
                            "AS answer_prompt FROM support_app.query_rewrites q "
                            "JOIN support_app.audit a USING(turn_id) WHERE q.turn_id=%s",
                            (turn,),
                        )
                    ).fetchone()
                    assert row is not None and row["prompt_version"] == 1
                    assert row["search_scope"] is None and row["category_keys"] is None
                    assert row["answer_prompt"] is None
                    text = await (
                        await conn.execute(
                            "SELECT text FROM support_app.turns WHERE id=%s", (turn,)
                        )
                    ).fetchone()
                    assert text is not None and text["text"] == "Retained fixture"

        run_async(verify())

        async def reject_tampering() -> None:
            """Verify checksum rejection inside a rolled-back private transaction."""
            async with await psycopg.AsyncConnection.connect(
                database.admin_dsn, autocommit=True, row_factory=dict_row
            ) as conn:
                with pytest.raises(MigrationError, match="schema_mismatch"):
                    async with conn.transaction():
                        await conn.execute(
                            "UPDATE support_meta.migrations SET checksum='changed' WHERE version=2"
                        )
                        await verify_schema(conn)
                await verify_schema(conn)

        run_async(reject_tampering())


@pytest.mark.parametrize("change", ["future", "gap"])
def test_native_rejects_unknown_migration_prefix(
    tmp_path: Path, owned_processes: OwnedProcesses, change: str
) -> None:
    """A future/partial migration history cannot be silently overwritten."""
    with owned_migration_database(tmp_path, owned_processes) as database:
        run_async(migrate(database.admin_dsn, "veritycx_support_test"))
        with psycopg.connect(database.admin_dsn, autocommit=True) as conn:
            if change == "future":
                conn.execute("INSERT INTO support_meta.migrations VALUES (99,'unknown')")
            else:
                conn.execute("DELETE FROM support_meta.migrations WHERE version=2")
        with pytest.raises(MigrationError, match="schema_mismatch"):
            run_async(migrate(database.admin_dsn, "veritycx_support_test"))
