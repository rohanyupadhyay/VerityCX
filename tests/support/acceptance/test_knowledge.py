"""Exercise supported, unsupported and conflicting questions through real owned processes."""

import os

import pytest

from veritycx.service.validation import validate_offline

pytestmark = pytest.mark.support_db


def test_knowledge_subprocesses(test_database_url: str) -> None:
    """Launch real API/worker children and assert only sanitized control-flow evidence."""
    result = validate_offline(dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url))
    assert result["cases_passed"] == 3
    assert result["provider"] == "deterministic"
