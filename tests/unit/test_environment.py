"""Exercise root-anchored, non-overwriting dotenv acquisition."""

import os
from pathlib import Path

import pytest

from veritycx import environment


def test_loads_from_absolute_root_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the declared root regardless of cwd and preserve explicit values and empties."""
    (tmp_path / ".env").write_text("EXPLICIT=dotenv\nEMPTY=\nADDED=from-file\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(environment, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("EXPLICIT", "process")
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.delenv("ADDED", raising=False)

    environment.load_project_environment()
    environment.load_project_environment()

    assert environment.PROJECT_ROOT / ".env" == tmp_path / ".env"
    assert os.environ["EXPLICIT"] == "process"
    assert os.environ["EMPTY"] == ""
    assert os.environ["ADDED"] == "from-file"


def test_missing_file_is_a_silent_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Accept a checkout without local dotenv configuration."""
    monkeypatch.setattr(environment, "PROJECT_ROOT", tmp_path)
    environment.load_project_environment()


def test_parse_failure_uses_value_safe_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject malformed input without disclosing its contents."""
    canary = "secret-canary-value"
    (tmp_path / ".env").write_text(f"BROKEN='{canary}\n", encoding="utf-8")
    monkeypatch.setattr(environment, "PROJECT_ROOT", tmp_path)

    with pytest.raises(environment.EnvironmentLoadError) as captured:
        environment.load_project_environment()

    assert str(captured.value) == "invalid_environment_file"
    assert canary not in str(captured.value)
