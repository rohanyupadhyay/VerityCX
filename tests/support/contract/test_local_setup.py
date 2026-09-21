"""Verify guarded local PostgreSQL bootstrap behavior through the public command."""

import json
import subprocess
import sys
from pathlib import Path

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
