"""Verify truthful durable handoff across a real owned worker restart."""

import os
from pathlib import Path

import pytest

from veritycx.service.validation import validate_handoff

pytestmark = pytest.mark.support_db


def test_handoff_subprocesses(test_database_url: str) -> None:
    """Run all six SC-004 scenarios through actual authenticated HTTP endpoints."""
    result = validate_handoff(dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url))
    assert result["cases_passed"] == 6
    assert result["delivery"] == "not_connected"
    assert result["prompt_version"] == 3


def test_handoff_metadata_uses_test_corpus_without_runtime_environment(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The standalone validator must not depend on the application's active corpus."""
    from veritycx.knowledge.configuration import source_mode
    from veritycx.knowledge.manifest import read_active

    monkeypatch.delenv("VERITYCX_DATABASE_URL", raising=False)
    root, cache, _ = source_mode("synthetic", validation=True)
    expected = read_active(root, cache).corpus_version
    app_active: Path = source_mode("synthetic")[1] / "active"
    before = app_active.read_bytes() if app_active.exists() else None
    result = validate_handoff(dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url))
    assert result["cases_passed"] == 6
    assert result["corpus_version"] == expected
    assert (app_active.read_bytes() if app_active.exists() else None) == before
