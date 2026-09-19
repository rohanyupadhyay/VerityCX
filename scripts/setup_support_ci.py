"""Create an isolated native CI database with separate migration and runtime credentials."""

import os
import secrets
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from veritycx.persistence.migrate import migrate
from veritycx.service.runtime import run_async


def main() -> None:
    """Initialize only a fresh CI-owned cluster and publish masked credentials to later steps."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("github_actions_required")
    prefix = Path(os.environ["PG_PREFIX"]).resolve()
    root = Path(".cache/support/ci").resolve()
    root.mkdir(parents=True, exist_ok=False)
    admin_password, runtime_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    password_file = root / "admin-password"
    password_file.write_text(admin_password, encoding="utf-8")
    password_file.chmod(0o600)
    for secret in (admin_password, runtime_password):
        print(f"::add-mask::{secret}")
    # Executables and all arguments are fixed trusted CI setup inputs, not customer content.
    subprocess.run(  # noqa: S603 - fixed trusted CI executable and arguments.
        [
            str(prefix / "bin/initdb"),
            "-D",
            str(root / "data"),
            "-U",
            "veritycx_admin",
            "-A",
            "scram-sha-256",
            "--pwfile",
            str(password_file),
            "--encoding=UTF8",
            "--no-locale",
        ],
        check=True,
    )
    subprocess.run(  # noqa: S603 - fixed trusted CI executable and arguments.
        [
            str(prefix / "bin/pg_ctl"),
            "-D",
            str(root / "data"),
            "-l",
            str(root / "postgres.log"),
            "-o",
            "-h 127.0.0.1 -p 55432",
            "-w",
            "start",
        ],
        check=True,
    )
    admin = make_conninfo(
        host="127.0.0.1",
        port=55432,
        user="veritycx_admin",
        password=admin_password,
        dbname="postgres",
    )
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL(
                "CREATE ROLE veritycx_support_test LOGIN PASSWORD {} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE"
            ).format(sql.Literal(runtime_password))
        )
        conn.execute("CREATE DATABASE veritycx_support_test OWNER veritycx_admin")
        conn.execute("REVOKE CONNECT ON DATABASE veritycx_support_test FROM PUBLIC")
        conn.execute("GRANT CONNECT ON DATABASE veritycx_support_test TO veritycx_support_test")
    migration = make_conninfo(admin, dbname="veritycx_support_test")
    runtime = make_conninfo(migration, user="veritycx_support_test", password=runtime_password)
    with psycopg.connect(migration, autocommit=True) as conn:
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    run_async(migrate(migration, "veritycx_support_test"))
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as output:
        output.write(
            f"VERITYCX_TEST_DATABASE_URL={runtime}\nVERITYCX_TEST_MIGRATION_DATABASE_URL={migration}\n"
        )


if __name__ == "__main__":
    main()
