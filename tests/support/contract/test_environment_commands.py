"""Prove management and validation commands load dotenv at their process boundary."""

import subprocess
import sys
from pathlib import Path
from typing import Protocol

import pytest
from scripts import manage_support, validate_support

from veritycx.environment import EnvironmentLoadError


class _CommandModule(Protocol):
    """Describe the entry-point interface shared by both root commands."""

    def main(self) -> int:
        """Run the command and return its process status."""


def test_commands_load_environment_before_project_reads() -> None:
    """Require both root scripts to invoke the shared loader before environment access."""
    root = Path(__file__).resolve().parents[3]
    for relative in ("scripts/manage_support.py", "scripts/validate_support.py"):
        source = (root / relative).read_text(encoding="utf-8")
        assert source.index("load_project_environment()") < source.index("os.environ")


@pytest.mark.parametrize(
    ("script", "arguments", "category"),
    [
        ("scripts/manage_support.py", ("db", "purge-expired"), "missing_runtime_configuration"),
        (
            "scripts/validate_support.py",
            ("--suite", "offline"),
            "dedicated_test_database_required",
        ),
    ],
)
def test_commands_preserve_missing_configuration_from_non_root_cwd(
    tmp_path: Path, script: str, arguments: tuple[str, ...], category: str
) -> None:
    """Resolve the root dotenv while retaining established missing-setting exits."""
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(root / script), *arguments],
        cwd=tmp_path,
        env={},
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == category
    assert result.stderr == ""


@pytest.mark.parametrize("command", [manage_support, validate_support])
def test_commands_sanitize_dotenv_failures(
    command: _CommandModule, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Return one value-free category when root dotenv parsing fails."""

    def fail_loading() -> None:
        """Stand in for a malformed local file without retaining its value."""
        raise EnvironmentLoadError("invalid_environment_file")

    monkeypatch.setattr(command, "load_project_environment", fail_loading)
    assert command.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "invalid_environment_file\n"
    assert captured.err == ""
