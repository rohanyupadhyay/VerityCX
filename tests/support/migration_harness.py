"""Own fresh native PostgreSQL clusters for non-destructive migration verification."""

import os
import secrets
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from tests.support.harness import OwnedProcesses, require_test_database
from veritycx import PROJECT_ROOT


@dataclass(frozen=True)
class MigrationTestDatabase:
    """Expose only redacted connections to an owned test database."""

    admin_dsn: str = field(repr=False)
    runtime_dsn: str = field(repr=False)


@contextmanager
def owned_migration_database(
    root: Path, processes: OwnedProcesses
) -> Iterator[MigrationTestDatabase]:
    """Initialize a private cluster and stop only its foreground process handle."""
    prefix = Path(os.environ.get("PG_PREFIX", str(PROJECT_ROOT / ".cache/support/postgresql")))
    binaries = prefix / "bin"
    if not all((binaries / name).is_file() for name in ("initdb", "postgres")):
        raise ValueError("native_postgresql_required")
    directory = root / "owned-migration-postgres"
    directory.mkdir(mode=0o700)
    password = secrets.token_urlsafe(32)
    runtime_password = secrets.token_urlsafe(32)
    password_file = directory / "password"
    password_file.write_text(password)
    password_file.chmod(0o600)
    data = directory / "data"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    result = subprocess.run(  # noqa: S603 - installed native binaries and private test-owned paths.
        [
            str(binaries / "initdb"),
            "-D",
            str(data),
            "-U",
            "veritycx_admin",
            "-A",
            "scram-sha-256",
            "--pwfile",
            str(password_file),
            "--encoding=UTF8",
            "--no-locale",
        ],
        env=environment,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("owned_postgres_initialization_failed")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    child = processes.start(
        [
            str(binaries / "postgres"),
            "-D",
            str(data),
            "-h",
            "127.0.0.1",
            "-p",
            str(port),
            "-c",
            "unix_socket_directories=",
        ],
        cwd=directory,
        env=environment,
    )
    bootstrap = make_conninfo(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user="veritycx_admin",
        password=password,
        connect_timeout=1,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            if child.poll() is not None or time.monotonic() > deadline:
                raise ValueError("owned_postgres_startup_failed")
            try:
                with psycopg.connect(bootstrap, autocommit=True) as conn:
                    conn.execute(
                        sql.SQL(
                            "CREATE ROLE veritycx_support_test LOGIN PASSWORD {} "
                            "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                        ).format(sql.Literal(runtime_password))
                    )
                    conn.execute("CREATE DATABASE veritycx_support_test OWNER veritycx_admin")
                break
            except psycopg.OperationalError:
                time.sleep(0.1)
        admin = make_conninfo(bootstrap, dbname="veritycx_support_test")
        runtime = make_conninfo(admin, user="veritycx_support_test", password=runtime_password)
        yield MigrationTestDatabase(require_test_database(admin), require_test_database(runtime))
    finally:
        processes.stop(child)
