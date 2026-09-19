"""Provide synthetic identities, documents and explicitly owned offline resources."""

import os
from collections.abc import Callable, Iterator
from uuid import UUID, uuid4

import pytest

from tests.support.harness import OwnedProcesses, require_test_database


@pytest.fixture
def synthetic_owner() -> UUID:
    """Return a fresh synthetic owner without sharing identity across tests."""
    return uuid4()


@pytest.fixture
def synthetic_document() -> Callable[[str], dict[str, str]]:
    """Return a factory for authored document envelopes with unique source IDs."""

    def make(content: str) -> dict[str, str]:
        """Build a closed synthetic document containing the supplied test passage."""
        return {"id": str(uuid4()), "title": "Synthetic policy", "content": content}

    return make


@pytest.fixture
def test_database_url() -> str:
    """Fail explicitly if the selected database suite has no dedicated test DSN."""
    return require_test_database(os.environ.get("VERITYCX_TEST_DATABASE_URL", ""))


@pytest.fixture
def owned_processes() -> Iterator[OwnedProcesses]:
    """Reap only children created by this fixture, even when the test fails."""
    processes = OwnedProcesses()
    try:
        yield processes
    finally:
        processes.close()
