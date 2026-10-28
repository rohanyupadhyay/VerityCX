"""Bootstrap owned local PostgreSQL databases and optional app demo configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from veritycx.knowledge.configuration import active_corpus
from veritycx.persistence.migrate import MigrationError, migrate
from veritycx.policy.sources import SourceError
from veritycx.service.auth import AuthError, authenticate, init_demo, load_principals
from veritycx.service.local_environment import LocalSetupError as LocalSetupError
from veritycx.service.local_environment import _app_environment_content as _app_environment_content
from veritycx.service.local_environment import _write_app_environment as _write_app_environment
from veritycx.service.runtime import run_async

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPPORT_ROOT = PROJECT_ROOT / ".cache" / "support"
POSTGRESQL_VERSION = "18.6"
POSTGRESQL_MAJOR = "18"
POSTGRESQL_PORT = 55432
OWNER_MARKER = ".veritycx-local-postgres"
ARCHIVE_NAME = f"postgresql-{POSTGRESQL_VERSION}.tar.bz2"
ARCHIVE_URL = f"https://ftp.postgresql.org/pub/source/v{POSTGRESQL_VERSION}/{ARCHIVE_NAME}"


@dataclass(frozen=True)
class SetupPaths:
    """Own every local bootstrap path beneath one explicit ignored root."""

    root: Path
    prefix: Path
    data: Path
    local: Path
    downloads: Path
    build: Path
    marker: Path
    credentials: Path
    environment: Path
    server_log: Path
    build_log: Path

    @classmethod
    def from_root(cls, root: Path) -> SetupPaths:
        """Resolve the complete owned layout without creating it."""
        resolved = root.resolve()
        local = resolved / "local"
        return cls(
            root=resolved,
            prefix=resolved / "postgresql",
            data=resolved / "pgdata",
            local=local,
            downloads=resolved / "downloads",
            build=resolved / "build",
            marker=resolved / OWNER_MARKER,
            credentials=local / "test-credentials.json",
            environment=local / "test.env",
            server_log=local / "postgres.log",
            build_log=local / "postgresql-build.log",
        )


def _expected_marker() -> dict[str, int | str]:
    return {"format": 1, "port": POSTGRESQL_PORT, "postgresql": POSTGRESQL_VERSION}


def _read_marker(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _layout_status(paths: SetupPaths) -> str:
    marker = _read_marker(paths.marker)
    if paths.data.exists() and marker != _expected_marker():
        return "local_support_setup_unowned"
    if not paths.root.exists() or not paths.data.exists():
        return "local_support_setup_missing"
    required = (
        paths.prefix / "bin" / "postgres",
        paths.data / "PG_VERSION",
        paths.environment,
    )
    if marker != _expected_marker() or not all(path.is_file() for path in required):
        return "local_support_setup_incomplete"
    try:
        if (paths.data / "PG_VERSION").read_text(encoding="utf-8").strip() != POSTGRESQL_MAJOR:
            return "local_support_setup_incomplete"
    except OSError:
        return "local_support_setup_incomplete"
    return "local_support_setup_ready"


def _write_private(path: Path, content: str, *, exclusive: bool = False) -> None:
    """Write an owned secret file privately from creation, optionally refusing overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC), 0o600
    )
    with os.fdopen(descriptor, mode, encoding="utf-8") as output:
        output.write(content)
    path.chmod(0o600)


def _ensure_app_auth(directory: Path, *, create: bool = True) -> Path:
    """Reuse complete valid demo identities, refusing partial or mismatched credentials."""
    targets = (directory / "auth.json", directory / "client-1.token", directory / "client-2.token")
    try:
        if directory.is_symlink():
            raise AuthError("invalid_auth_configuration")
        if not any(path.exists() or path.is_symlink() for path in targets) and create:
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            directory.chmod(0o700)
            targets = init_demo(directory)
        if any(not path.is_file() or path.is_symlink() for path in targets):
            raise AuthError("invalid_auth_configuration")
        principals = load_principals(targets[0])
        owners = {
            authenticate("Bearer " + token.read_text(encoding="utf-8").strip(), principals)
            for token in targets[1:]
        }
        if len(owners) != 2:
            raise AuthError("invalid_auth_configuration")
        if create:
            directory.chmod(0o700)
            for path in targets:
                path.chmod(0o600)
        return targets[0]
    except (AuthError, OSError, UnicodeError):
        raise LocalSetupError("local_support_app_auth_invalid") from None


def _claim_layout(paths: SetupPaths) -> None:
    marker = _read_marker(paths.marker)
    if paths.data.exists() and marker != _expected_marker():
        raise LocalSetupError("local_support_setup_unowned")
    if paths.marker.exists() and marker != _expected_marker():
        raise LocalSetupError("local_support_setup_unowned")
    paths.local.mkdir(parents=True, exist_ok=True)
    if not paths.marker.exists():
        _write_private(
            paths.marker, json.dumps(_expected_marker(), sort_keys=True) + "\n", exclusive=True
        )


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed HTTPS URL.
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _expected_archive_digest(checksum: Path) -> str:
    fields = checksum.read_text(encoding="ascii").strip().split()
    if len(fields) < 1 or len(fields[0]) != 64:
        raise LocalSetupError("local_support_download_invalid")
    digest = fields[0].lower()
    if any(character not in "0123456789abcdef" for character in digest):
        raise LocalSetupError("local_support_download_invalid")
    return digest


def _archive_digest(archive: Path) -> str:
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    command: list[str], *, cwd: Path, log: Path, environment: dict[str, str] | None = None
) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as output:
        subprocess.run(  # noqa: S603 - executable paths are fixed project-owned build inputs.
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=True,
            env=environment,
        )


def _build_environment(paths: SetupPaths) -> dict[str, str]:
    environment = dict(os.environ)
    if shutil.which("bison") is not None and shutil.which("flex") is not None:
        return environment
    tools = paths.root / "tools"
    binaries = tools / "usr" / "bin"
    if not (binaries / "bison").is_file() or not (binaries / "flex").is_file():
        if shutil.which("apt-get") is None or shutil.which("dpkg-deb") is None:
            raise LocalSetupError("local_support_build_tools_missing")
        packages = tools / "packages"
        packages.mkdir(parents=True, exist_ok=True)
        _run(["apt-get", "download", "bison", "flex"], cwd=packages, log=paths.build_log)
        archives = sorted(packages.glob("bison_*.deb")) + sorted(packages.glob("flex_*.deb"))
        if len(archives) < 2:
            raise LocalSetupError("local_support_build_tools_missing")
        for archive in archives:
            _run(
                ["dpkg-deb", "-x", str(archive), str(tools)],
                cwd=packages,
                log=paths.build_log,
            )
    if not (binaries / "bison").is_file() or not (binaries / "flex").is_file():
        raise LocalSetupError("local_support_build_tools_missing")
    environment["PATH"] = f"{binaries}{os.pathsep}{environment.get('PATH', '')}"
    environment["BISON_PKGDATADIR"] = str(tools / "usr" / "share" / "bison")
    return environment


def _install_postgresql(paths: SetupPaths) -> None:
    postgres = paths.prefix / "bin" / "postgres"
    if postgres.is_file():
        result = subprocess.run(  # noqa: S603 - project-owned executable under the marked root.
            [str(postgres), "--version"], capture_output=True, text=True, check=True
        )
        if result.stdout.strip() != f"postgres (PostgreSQL) {POSTGRESQL_VERSION}":
            raise LocalSetupError("local_support_postgresql_version_mismatch")
        return

    archive = paths.downloads / ARCHIVE_NAME
    checksum = paths.downloads / f"{ARCHIVE_NAME}.sha256"
    if not checksum.is_file():
        _download(f"{ARCHIVE_URL}.sha256", checksum)
    if not archive.is_file():
        _download(ARCHIVE_URL, archive)
    if _archive_digest(archive) != _expected_archive_digest(checksum):
        raise LocalSetupError("local_support_download_invalid")

    source = paths.build / f"postgresql-{POSTGRESQL_VERSION}"
    if not source.is_dir():
        paths.build.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:bz2") as package:
            package.extractall(paths.build, filter="data")
    configure = source / "configure"
    if not configure.is_file():
        raise LocalSetupError("local_support_download_invalid")
    environment = _build_environment(paths)
    jobs = max(1, min(os.cpu_count() or 1, 4))
    _run(
        [
            str(configure),
            f"--prefix={paths.prefix}",
            "--without-readline",
            "--without-icu",
            "--without-zlib",
        ],
        cwd=source,
        log=paths.build_log,
        environment=environment,
    )
    _run(["make", f"-j{jobs}"], cwd=source, log=paths.build_log, environment=environment)
    _run(["make", "install"], cwd=source, log=paths.build_log, environment=environment)


def _load_or_create_credentials(paths: SetupPaths) -> dict[str, str]:
    if paths.credentials.is_file():
        try:
            value = json.loads(paths.credentials.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LocalSetupError("local_support_credentials_invalid") from error
        if isinstance(value, dict) and all(
            isinstance(value.get(key), str) and value[key]
            for key in ("admin_password", "runtime_password")
        ):
            return {key: str(value[key]) for key in ("admin_password", "runtime_password")}
        raise LocalSetupError("local_support_credentials_invalid")
    if paths.data.exists():
        raise LocalSetupError("local_support_setup_incomplete")
    credentials = {
        "admin_password": secrets.token_urlsafe(32),
        "runtime_password": secrets.token_urlsafe(32),
    }
    _write_private(
        paths.credentials, json.dumps(credentials, sort_keys=True) + "\n", exclusive=True
    )
    return credentials


def _connection_strings(
    credentials: dict[str, str], runtime_role: str = "veritycx_support_test"
) -> tuple[str, str, str]:
    """Build fixed local admin/migration/runtime DSNs without exposing passwords."""
    if runtime_role not in {"veritycx_support", "veritycx_support_test"}:
        raise LocalSetupError("local_support_setup_unowned")
    admin = make_conninfo(
        host="127.0.0.1",
        port=POSTGRESQL_PORT,
        user="veritycx_admin",
        password=credentials["admin_password"],
        dbname="postgres",
    )
    migration = make_conninfo(admin, dbname=runtime_role)
    runtime = make_conninfo(
        migration,
        user=runtime_role,
        password=credentials["runtime_password"],
    )
    return admin, migration, runtime


def _write_environment(paths: SetupPaths, migration: str, runtime: str) -> None:
    content = (
        f"export VERITYCX_TEST_DATABASE_URL={shlex.quote(runtime)}\n"
        f"export VERITYCX_TEST_MIGRATION_DATABASE_URL={shlex.quote(migration)}\n"
    )
    _write_private(paths.environment, content)


def _initialize_cluster(paths: SetupPaths, admin_password: str) -> None:
    if paths.data.exists():
        return
    password_file = paths.local / "initdb-password"
    _write_private(password_file, admin_password + "\n")
    try:
        _run(
            [
                str(paths.prefix / "bin" / "initdb"),
                "-D",
                str(paths.data),
                "-U",
                "veritycx_admin",
                "-A",
                "scram-sha-256",
                "--pwfile",
                str(password_file),
                "--encoding=UTF8",
                "--no-locale",
            ],
            cwd=paths.root,
            log=paths.build_log,
        )
    finally:
        password_file.unlink(missing_ok=True)


def _start_cluster(paths: SetupPaths) -> None:
    pg_ctl = paths.prefix / "bin" / "pg_ctl"
    status = subprocess.run(  # noqa: S603 - project-owned executable under the marked root.
        [str(pg_ctl), "-D", str(paths.data), "status"],
        cwd=paths.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if status.returncode == 0:
        return
    _run(
        [
            str(pg_ctl),
            "-D",
            str(paths.data),
            "-l",
            str(paths.server_log),
            "-o",
            f"-h 127.0.0.1 -p {POSTGRESQL_PORT}",
            "-w",
            "start",
        ],
        cwd=paths.root,
        log=paths.build_log,
    )


def _provision_database(
    admin: str, migration: str, runtime_password: str, runtime_role: str = "veritycx_support_test"
) -> None:
    """Provision one fixed owned database and migrate it without dropping existing data."""
    if runtime_role not in {"veritycx_support", "veritycx_support_test"}:
        raise LocalSetupError("local_support_setup_unowned")
    identifier = sql.Identifier(runtime_role)
    with psycopg.connect(admin, autocommit=True) as connection:
        cursor = connection.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (runtime_role,)
        )
        database = cursor.fetchone()
        if database is not None and database[0] != "veritycx_admin":
            raise LocalSetupError("local_support_setup_unowned")
        cursor = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=%s",
            (runtime_role,),
        )
        role = cursor.fetchone()
        if role is None:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(identifier, sql.Literal(runtime_password))
            )
        elif runtime_role == "veritycx_support_test":
            connection.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                    identifier, sql.Literal(runtime_password)
                )
            )
        elif any(role):
            raise LocalSetupError("local_support_setup_unowned")
        if database is None:
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER veritycx_admin").format(identifier)
            )
        connection.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(identifier))
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(identifier, identifier)
        )
    with psycopg.connect(migration, autocommit=True) as connection:
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    run_async(migrate(migration, runtime_role))


def _app_credentials(paths: SetupPaths, admin: str, *, create: bool) -> dict[str, str]:
    """Keep app credentials stable and refuse adoption of an unregistered database/role."""
    path = paths.local / "app-credentials.json"
    if path.is_symlink():
        raise LocalSetupError("local_support_app_credentials_invalid")
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise LocalSetupError("local_support_app_credentials_invalid") from None
        if (
            not isinstance(value, dict)
            or set(value) != {"runtime_password"}
            or not isinstance(value["runtime_password"], str)
            or not value["runtime_password"]
        ):
            raise LocalSetupError("local_support_app_credentials_invalid")
        return {"runtime_password": value["runtime_password"]}
    if not create:
        raise LocalSetupError("local_support_app_setup_incomplete")
    with psycopg.connect(admin, autocommit=True) as connection:
        row = connection.execute(
            "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname='veritycx_support') "
            "OR EXISTS (SELECT FROM pg_database WHERE datname='veritycx_support')"
        ).fetchone()
        if row is None or row[0]:
            raise LocalSetupError("local_support_setup_unowned")
    credentials = {"runtime_password": secrets.token_urlsafe(32)}
    # Persist before provisioning so an interrupted first setup can be resumed.
    _write_private(path, json.dumps(credentials) + "\n", exclusive=True)
    return credentials


def _app_values(paths: SetupPaths, *, create: bool) -> dict[str, str]:
    """Derive app settings using the cluster admin and separate saved runtime password."""
    credentials = _load_or_create_credentials(paths)
    admin, _, _ = _connection_strings(credentials)
    app_credentials = _app_credentials(paths, admin, create=create)
    _, migration, runtime = _connection_strings(
        {**credentials, **app_credentials}, "veritycx_support"
    )
    return {
        "VERITYCX_DATABASE_URL": runtime,
        "VERITYCX_MIGRATION_DATABASE_URL": migration,
        "VERITYCX_AUTH_FILE": str(paths.root / "credentials" / "auth.json"),
    }


def _setup_app(paths: SetupPaths) -> None:
    """Provision the separate app database, reuse demo auth and fill root dotenv settings."""
    values = _app_values(paths, create=True)
    environment = PROJECT_ROOT / ".env"
    # Detect configuration conflicts before provisioning the app database or demo auth.
    _app_environment_content(environment, values)
    _ensure_app_auth(paths.root / "credentials")
    cluster_credentials = _load_or_create_credentials(paths)
    admin, _, _ = _connection_strings(cluster_credentials)
    app_credentials = _app_credentials(paths, admin, create=False)
    _provision_database(
        admin,
        values["VERITYCX_MIGRATION_DATABASE_URL"],
        app_credentials["runtime_password"],
        "veritycx_support",
    )
    # Confirm the saved password works; never reset an existing app role on rerun.
    with psycopg.connect(values["VERITYCX_DATABASE_URL"], connect_timeout=5):
        pass
    _write_app_environment(environment, values)


def _app_layout_status(paths: SetupPaths) -> str:
    """Read app files without connecting to PostgreSQL or generating credentials."""
    try:
        if not paths.credentials.is_file():
            return "local_support_app_setup_incomplete"
        values = _app_values(paths, create=False)
        _ensure_app_auth(paths.root / "credentials", create=False)
        environment = PROJECT_ROOT / ".env"
        if not environment.is_file():
            return "local_support_app_setup_incomplete"
        if _app_environment_content(environment, values) != environment.read_text(encoding="utf-8"):
            return "local_support_app_setup_incomplete"
    except LocalSetupError as error:
        return str(error)
    except (OSError, UnicodeError):
        return "local_support_app_setup_incomplete"
    return "local_support_app_setup_ready"


def _bootstrap(paths: SetupPaths) -> None:
    _claim_layout(paths)
    _install_postgresql(paths)
    credentials = _load_or_create_credentials(paths)
    admin, migration, runtime = _connection_strings(credentials)
    _initialize_cluster(paths, credentials["admin_password"])
    _start_cluster(paths)
    _provision_database(admin, migration, credentials["runtime_password"])
    _write_environment(paths, migration, runtime)


def main() -> int:
    """Create or inspect the project-owned local support database."""
    parser = argparse.ArgumentParser(description="Set up local VerityCX support PostgreSQL")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SUPPORT_ROOT,
        help="owned support-cache root (default: .cache/support)",
    )
    parser.add_argument(
        "--check", action="store_true", help="inspect existing setup without changing it"
    )
    parser.add_argument(
        "--app",
        action="store_true",
        help="also provision the separate app database, demo auth and root .env",
    )
    arguments = parser.parse_args()
    paths = SetupPaths.from_root(arguments.root)
    status = _layout_status(paths)
    if arguments.check:
        if arguments.app and status == "local_support_setup_ready":
            status = _app_layout_status(paths)
        print(status)
        return 0 if status in {"local_support_setup_ready", "local_support_app_setup_ready"} else 1
    if status == "local_support_setup_unowned":
        print(status)
        return 1
    try:
        _bootstrap(paths)
        if arguments.app:
            _setup_app(paths)
    except (LocalSetupError, MigrationError) as error:
        print(str(error))
        return 1
    except (
        OSError,
        psycopg.Error,
        subprocess.SubprocessError,
        tarfile.TarError,
        urllib.error.URLError,
        UnicodeError,
    ):
        print("local_support_setup_failed")
        return 1
    print("local_support_setup_ready")
    print(f"environment={paths.environment}")
    if arguments.app:
        print("local_support_app_setup_ready")
        print(f"app_environment={PROJECT_ROOT / '.env'}")
        try:
            active_corpus("synthetic")
            print("corpus=approved")
        except (SourceError, OSError, ValueError):
            print("corpus=approval_required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
