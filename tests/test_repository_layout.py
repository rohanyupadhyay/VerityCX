"""Guard the repository-root command contract without reading external data."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "arguments",
    [
        ("scripts/setup_tau3_data.py", "--help"),
        ("scripts/setup_tau3_data.py", "--check", "--help"),
        ("scripts/inspect_tau3_banking_data.py", "--help"),
    ],
)
def test_documented_commands_start_from_git_root(arguments: tuple[str, ...]) -> None:
    """Catch a nested project by running real CLI parsers from Git's top level."""
    git_executable = shutil.which("git")
    assert git_executable is not None, "Git is a documented project prerequisite"
    # Only the resolved Git executable and fixed, non-shell arguments are used.
    detected = subprocess.run(  # noqa: S603
        [git_executable, "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        shell=False,
    )
    repository_root = Path(detected.stdout.strip())
    # The locked environment supplies Python; help avoids cache or network access.
    result = subprocess.run(  # noqa: S603
        [sys.executable, *arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        shell=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert result.stderr == ""
