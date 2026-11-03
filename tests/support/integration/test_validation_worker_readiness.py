"""Require the owned load worker to be ready despite other fresh heartbeats."""

import time
from uuid import uuid4

import httpx
import psycopg
import pytest

from veritycx.service import validation

pytestmark = pytest.mark.support_db


def test_owned_worker_readiness_ignores_foreign_fresh_heartbeat(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An API-ready response cannot start load timing before this worker advertises itself."""
    owned, foreign = uuid4(), uuid4()
    polls: list[int] = []

    def response(request: httpx.Request) -> httpx.Response:
        """Represent health readiness satisfied by the preceding worker's heartbeat."""
        polls.append(1)
        return httpx.Response(200, json={"status": "ready"})

    def advertise_owned(seconds: float) -> None:
        """Advertise the owned worker only after the first readiness check waits."""
        assert len(polls) == 1
        with psycopg.connect(test_database_url) as conn:
            conn.execute(
                "INSERT INTO support_app.worker_heartbeats VALUES (%s,clock_timestamp())",
                (owned,),
            )

    try:
        with psycopg.connect(test_database_url) as conn:
            conn.execute(
                "INSERT INTO support_app.worker_heartbeats VALUES (%s,clock_timestamp())",
                (foreign,),
            )
        monkeypatch.setattr(time, "sleep", advertise_owned)
        with httpx.Client(
            transport=httpx.MockTransport(response), base_url="http://test"
        ) as client:
            validation.wait_ready(
                client,
                validation.ProcessOwner({}),
                worker_identity=(test_database_url, owned),
            )
        assert len(polls) == 2
    finally:
        with psycopg.connect(test_database_url) as conn:
            conn.execute(
                "DELETE FROM support_app.worker_heartbeats WHERE worker_id IN (%s,%s)",
                (owned, foreign),
            )
