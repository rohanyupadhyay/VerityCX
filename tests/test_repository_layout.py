"""Guard the repository-root command contract without reading external data."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


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


def test_environment_contract_is_part_of_every_quality_host() -> None:
    """Require the documented checker and GH-5 artifacts in the three-host quality workflow."""
    workflow = (REPOSITORY_ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    workflow_docs = (REPOSITORY_ROOT / ".github/workflows/README.md").read_text(encoding="utf-8")
    root_docs = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    command = "uv run python scripts/check_environment_contract.py"

    assert command in workflow
    assert command in workflow_docs
    assert command in root_docs
    assert "specs/gh-5-env-support" in workflow
    for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
        assert runner in workflow


def test_local_dotenv_is_ignored_but_example_is_tracked() -> None:
    """Keep developer values untracked while preserving the public template contract."""
    git_executable = shutil.which("git")
    assert git_executable is not None, "Git is a documented project prerequisite"
    ignored = subprocess.run(  # noqa: S603
        [git_executable, "check-ignore", "-q", ".env"],
        cwd=REPOSITORY_ROOT,
        check=False,
        shell=False,
    )
    example = subprocess.run(  # noqa: S603
        [git_executable, "check-ignore", "-q", ".env.example"],
        cwd=REPOSITORY_ROOT,
        check=False,
        shell=False,
    )
    assert ignored.returncode == 0
    assert example.returncode == 1
