"""Manage explicit support database migrations without importing runtime credentials."""

import argparse
import os
from typing import Literal

from psycopg import Error
from psycopg.conninfo import conninfo_to_dict

from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import approve, load_manifest, prepare
from veritycx.persistence.database import database_pool
from veritycx.persistence.maintenance import purge_expired
from veritycx.persistence.migrate import MigrationError, migrate
from veritycx.policy.sources import SourceError
from veritycx.service.auth import AuthError, init_demo
from veritycx.service.configuration import PROJECT_ROOT
from veritycx.service.runtime import run_async


def main() -> int:
    """Dispatch root management commands and report sanitized expected failures."""
    parser = argparse.ArgumentParser(description="Manage local durable support")
    commands = parser.add_subparsers(dest="command", required=True)
    database = commands.add_parser("db")
    database_commands = database.add_subparsers(dest="operation", required=True)
    database_commands.add_parser("migrate")
    database_commands.add_parser("purge-expired")
    auth = commands.add_parser("auth")
    auth.add_subparsers(dest="operation", required=True).add_parser("init-demo")
    corpus = commands.add_parser("corpus")
    corpus_commands = corpus.add_subparsers(dest="operation", required=True)
    prepare_parser = corpus_commands.add_parser("prepare")
    prepare_parser.add_argument("--mode", choices=["synthetic", "official"], required=True)
    corpus_commands.add_parser("approve").add_argument("--hash", required=True)
    arguments = parser.parse_args()
    if arguments.command == "corpus":
        try:
            if arguments.operation == "prepare":
                mode: Literal["synthetic", "official"] = (
                    "official" if arguments.mode == "official" else "synthetic"
                )
                root, cache, pin = source_mode(mode)
                manifest = prepare(root, cache, mode, pin)
                print(
                    f"mode={mode} documents={len(manifest.entries)} hash={manifest.aggregate_hash}"
                )
            else:
                digest = arguments.hash
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                ):
                    raise SourceError("invalid_manifest_hash")
                candidates = [
                    (
                        PROJECT_ROOT
                        / ".cache"
                        / "support"
                        / "corpora"
                        / mode
                        / digest
                        / "manifest.json"
                    )
                    for mode in ("synthetic", "official")
                ]
                found = [path for path in candidates if path.is_file()]
                if len(found) != 1:
                    raise SourceError("invalid_manifest_hash")
                manifest = load_manifest(found[0])
                root, cache, pin = source_mode(manifest.mode)
                if manifest.source_pin != pin:
                    raise SourceError("corpus_changed")
                approve(root, cache, digest)
                print("corpus_approved")
        except (SourceError, OSError):
            print("corpus_unavailable")
            return 1
        return 0
    if arguments.command == "auth":
        try:
            paths = init_demo(PROJECT_ROOT / ".cache" / "support" / "credentials")
        except (AuthError, OSError):
            print("credential_setup_failed")
            return 1
        for path in paths:
            print(path.relative_to(PROJECT_ROOT))
        return 0
    if arguments.operation == "purge-expired":
        runtime_dsn = os.environ.get("VERITYCX_DATABASE_URL")
        if not runtime_dsn:
            print("missing_runtime_configuration")
            return 1

        async def purge() -> int:
            """Use only the runtime connection and deletion-only maintenance guard."""
            async with database_pool(runtime_dsn) as pool:
                return await purge_expired(pool)

        try:
            print(f"purged={run_async(purge())}")
        except (Error, OSError, ValueError):
            print("maintenance_unavailable")
            return 1
        return 0
    admin = os.environ.get("VERITYCX_MIGRATION_DATABASE_URL")
    if not admin:
        print("missing_migration_configuration")
        return 1
    try:
        database_name = conninfo_to_dict(admin).get("dbname")
        if not isinstance(database_name, str) or database_name not in {
            "veritycx_support",
            "veritycx_support_test",
        }:
            print("invalid_migration_database")
            return 1
        run_async(migrate(admin, database_name))
    except MigrationError as error:
        print(str(error))
        return 1
    except (Error, OSError, ValueError):
        print("migration_unavailable")
        return 1
    print("migration_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
