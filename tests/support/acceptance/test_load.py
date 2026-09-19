"""Measure thirty queue-inclusive deterministic turns across ten concurrent conversations."""

import os

import pytest

from veritycx.service.validation import validate_load

pytestmark = pytest.mark.support_db


def test_deterministic_load(test_database_url: str) -> None:
    """Require nearest-rank p95 at most five seconds with no cross-owner leakage."""
    result = validate_load(dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url))
    assert result["turns"] == 30
    assert result["leaks"] == 0
    assert isinstance(result["p95_seconds"], float) and result["p95_seconds"] <= 5
