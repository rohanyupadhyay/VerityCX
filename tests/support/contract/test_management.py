"""Verify root management invocation, safe exits and administrative DSN isolation."""

import os
import subprocess
import sys
from pathlib import Path


def test_missing_admin_is_safe() -> None:
    """Runtime credentials cannot substitute for the explicit migration credential."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VERITYCX_MIGRATION_DATABASE_URL"}
    }
    env["VERITYCX_DATABASE_URL"] = "secret-canary"
    result = subprocess.run(
        [sys.executable, "scripts/manage_support.py", "db", "migrate"],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "missing_migration_configuration"
    assert "secret-canary" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_corpus_rejects_arbitrary_source() -> None:
    """The public CLI must expose modes, never arbitrary filesystem source paths."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/manage_support.py",
            "corpus",
            "prepare",
            "--mode",
            "synthetic",
            "--source",
            "untrusted",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --source" in result.stderr
