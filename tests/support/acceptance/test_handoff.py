"""Verify truthful durable handoff across a real owned worker restart."""

import os

import pytest

from veritycx.service.validation import validate_handoff

pytestmark = pytest.mark.support_db


def test_handoff_subprocesses(test_database_url: str) -> None:
    """Run all six SC-004 scenarios through actual authenticated HTTP endpoints."""
    result = validate_handoff(dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url))
    assert result["cases_passed"] == 6
    assert result["delivery"] == "not_connected"
