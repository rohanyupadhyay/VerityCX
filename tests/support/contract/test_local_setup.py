"""Verify guarded local PostgreSQL bootstrap behavior through the public command."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from scripts import setup_support_local as setup

from veritycx.persistence.migrate import MigrationError
from veritycx.service.auth import authenticate, load_principals

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_check_reports_missing_setup_without_creating_files(tmp_path: Path) -> None:
    """A read-only check must distinguish an absent setup from a failed bootstrap."""
    support_root = tmp_path / "support"

    result = subprocess.run(  # noqa: S603 - fixed local Python command under test.
        [
            sys.executable,
            "scripts/setup_support_local.py",
            "--root",
            str(support_root),
            "--check",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == "local_support_setup_missing\n"
    assert result.stderr == ""
    assert not support_root.exists()


def test_check_refuses_an_unmarked_existing_cluster(tmp_path: Path) -> None:
    """An existing PostgreSQL data directory without our marker must never be adopted."""
    support_root = tmp_path / "support"
    data = support_root / "pgdata"
    data.mkdir(parents=True)
    (data / "PG_VERSION").write_text("18\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - fixed local Python command under test.
        [
            sys.executable,
            "scripts/setup_support_local.py",
            "--root",
            str(support_root),
            "--check",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == "local_support_setup_unowned\n"
    assert result.stderr == ""
    assert (data / "PG_VERSION").read_text(encoding="utf-8") == "18\n"


def test_setup_refuses_an_unmarked_existing_cluster(tmp_path: Path) -> None:
    """The mutating command must stop before touching an unfamiliar data directory."""
    support_root = tmp_path / "support"
    data = support_root / "pgdata"
    data.mkdir(parents=True)
    canary = data / "do-not-touch"
    canary.write_text("owned elsewhere\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - fixed local Python command under test.
        [sys.executable, "scripts/setup_support_local.py", "--root", str(support_root)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == "local_support_setup_unowned\n"
    assert result.stderr == ""
    assert canary.read_text(encoding="utf-8") == "owned elsewhere\n"


def test_check_reports_a_complete_owned_layout(tmp_path: Path) -> None:
    """A complete marked setup is recognized without starting or changing it."""
    support_root = tmp_path / "support"
    postgres = support_root / "postgresql" / "bin" / "postgres"
    postgres.parent.mkdir(parents=True)
    postgres.write_text("binary placeholder\n", encoding="utf-8")
    data = support_root / "pgdata"
    data.mkdir()
    (data / "PG_VERSION").write_text("18\n", encoding="utf-8")
    local = support_root / "local"
    local.mkdir()
    (local / "test.env").write_text("private configuration\n", encoding="utf-8")
    (support_root / ".veritycx-local-postgres").write_text(
        json.dumps({"format": 1, "port": 55432, "postgresql": "18.6"}) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603 - fixed local Python command under test.
        [
            sys.executable,
            "scripts/setup_support_local.py",
            "--root",
            str(support_root),
            "--check",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "local_support_setup_ready\n"
    assert result.stderr == ""


def test_app_check_reports_missing_setup_without_writing(tmp_path: Path) -> None:
    """App checks must accept the flag without installing or generating secrets."""
    support_root = tmp_path / "support"
    result = subprocess.run(  # noqa: S603 - fixed local Python command under test.
        [
            sys.executable,
            "scripts/setup_support_local.py",
            "--root",
            str(support_root),
            "--app",
            "--check",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == "local_support_setup_missing\n"
    assert result.stderr == ""
    assert not support_root.exists()


def test_app_environment_preserves_values_and_is_idempotent(tmp_path: Path) -> None:
    """Setup fills empty settings while preserving comments, unrelated secrets and reruns."""
    path = tmp_path / ".env"
    path.write_text("# local settings\nOTHER='keep-me'\nVERITYCX_DATABASE_URL=\n", encoding="utf-8")
    values = {
        "VERITYCX_DATABASE_URL": "host=127.0.0.1 password='synthetic value'",
        "VERITYCX_AUTH_FILE": str(tmp_path / "demo path" / "auth.json"),
        "VERITYCX_MIGRATION_DATABASE_URL": "host=127.0.0.1 user=admin",
    }
    setup._write_app_environment(path, values)
    original = path.read_bytes()
    setup._write_app_environment(path, values)
    assert path.read_bytes() == original
    loaded = dotenv_values(path)
    assert loaded["OTHER"] == "keep-me"
    assert "# local settings" in path.read_text(encoding="utf-8")
    for key, value in values.items():
        assert loaded[key] == value
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "content",
    [
        "VERITYCX_DATABASE_URL='existing-secret'\n",
        "BROKEN='secret\n",
        "VERITYCX_DATABASE_URL=\nVERITYCX_DATABASE_URL=\n",
    ],
)
def test_app_environment_refuses_conflicts_without_replacing(
    tmp_path: Path,
    content: str,
) -> None:
    """A conflict, malformed file or duplicate target must not lose existing configuration."""
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(setup.LocalSetupError) as caught:
        setup._write_app_environment(path, {"VERITYCX_DATABASE_URL": "new-secret"})
    assert str(caught.value) == "local_support_app_configuration_conflict"
    assert path.read_text(encoding="utf-8") == content


def test_app_authentication_reuses_the_same_identities(tmp_path: Path) -> None:
    """Rerunning app setup must keep both clients able to access their conversations."""
    directory = tmp_path / "credentials"
    auth = setup._ensure_app_auth(directory)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    assert setup._ensure_app_auth(directory) == auth
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
    principals = load_principals(auth)
    first = authenticate("Bearer " + (directory / "client-1.token").read_text().strip(), principals)
    second = authenticate(
        "Bearer " + (directory / "client-2.token").read_text().strip(), principals
    )
    assert first != second
    if sys.platform != "win32":
        assert all(path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir())


def test_app_authentication_refuses_partial_credentials(tmp_path: Path) -> None:
    """Incomplete local credentials must be preserved for recovery rather than replaced."""
    directory = tmp_path / "credentials"
    directory.mkdir()
    token = directory / "client-1.token"
    token.write_text("keep-existing-token\n", encoding="utf-8")
    with pytest.raises(setup.LocalSetupError, match="local_support_app_auth_invalid"):
        setup._ensure_app_auth(directory)
    assert token.read_text(encoding="utf-8") == "keep-existing-token\n"
    assert not (directory / "auth.json").exists()


def test_app_connections_use_a_separate_database_and_role() -> None:
    """App setup must not point the interactive service at dedicated test storage."""
    admin, migration, runtime = setup._connection_strings(
        {"admin_password": "synthetic-admin", "runtime_password": "synthetic-runtime"},
        "veritycx_support",
    )
    admin_fields = conninfo_to_dict(admin)
    migration_fields = conninfo_to_dict(migration)
    runtime_fields = conninfo_to_dict(runtime)
    assert admin_fields["dbname"] == "postgres"
    assert migration_fields["dbname"] == runtime_fields["dbname"] == "veritycx_support"
    assert migration_fields["user"] == "veritycx_admin"
    assert runtime_fields["user"] == "veritycx_support"
    assert runtime_fields["password"] != migration_fields["password"]


def test_app_credentials_reuse_saved_password_without_connecting(tmp_path: Path) -> None:
    """Reading saved app credentials must preserve them and need no database connection."""
    paths = setup.SetupPaths.from_root(tmp_path)
    paths.local.mkdir()
    saved = paths.local / "app-credentials.json"
    content = '{"runtime_password":"synthetic-existing-password"}\n'
    saved.write_text(content, encoding="utf-8")
    assert setup._app_credentials(paths, "invalid-dsn", create=True) == {
        "runtime_password": "synthetic-existing-password"
    }
    assert saved.read_text(encoding="utf-8") == content


def test_app_environment_refuses_symlink_targets(tmp_path: Path) -> None:
    """A root dotenv link must never redirect setup writes into another file."""
    target = tmp_path / "private"
    target.write_text("preserve\n", encoding="utf-8")
    link = tmp_path / ".env"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("local symlink privilege required")
    with pytest.raises(setup.LocalSetupError, match="local_support_app_configuration_conflict"):
        setup._write_app_environment(link, {"VERITYCX_DATABASE_URL": "synthetic"})
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "preserve\n"


def test_app_authentication_refuses_linked_directories(tmp_path: Path) -> None:
    """App setup must not chmod or populate a credentials directory owned elsewhere."""
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = tmp_path / "credentials"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("local symlink privilege required")
    with pytest.raises(setup.LocalSetupError, match="local_support_app_auth_invalid"):
        setup._ensure_app_auth(link)
    assert not list(target.iterdir())


def test_app_check_does_not_repair_partial_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read-only app check must report missing auth without issuing new credentials."""
    paths = setup.SetupPaths.from_root(tmp_path / "support")
    paths.local.mkdir(parents=True)
    paths.credentials.write_text(
        '{"admin_password":"synthetic-admin","runtime_password":"synthetic-test"}',
        encoding="utf-8",
    )
    (paths.local / "app-credentials.json").write_text(
        '{"runtime_password":"synthetic-app"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(setup, "PROJECT_ROOT", tmp_path)
    assert setup._app_layout_status(paths) == "local_support_app_auth_invalid"
    assert not (paths.root / "credentials").exists()
    assert not (tmp_path / ".env").exists()


def test_app_environment_rejects_literal_interpolation_paths(tmp_path: Path) -> None:
    """Generated values must not change when the app's dotenv loader interpolates them."""
    path = tmp_path / ".env"
    with pytest.raises(setup.LocalSetupError, match="local_support_app_configuration_conflict"):
        setup._write_app_environment(
            path, {"VERITYCX_AUTH_FILE": str(tmp_path / "${LOCAL_SETUP_PATH}" / "auth.json")}
        )
    assert not path.exists()


def test_setup_reports_migration_mismatch_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Database migration mismatches must use the command's safe failure boundary."""

    def fail_migration(paths: setup.SetupPaths) -> None:
        """Represent an operational schema mismatch at the database bootstrap boundary."""
        raise MigrationError("schema_mismatch")

    monkeypatch.setattr(setup, "_bootstrap", fail_migration)
    monkeypatch.setattr(sys, "argv", ["setup_support_local.py", "--root", str(tmp_path), "--app"])
    assert setup.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "schema_mismatch\n"
    assert captured.err == ""
