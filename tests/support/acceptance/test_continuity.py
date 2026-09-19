"""Verify storage-outage denial and stable exhausted-budget results."""

from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.worker import process_job
from veritycx.persistence.attempts import AttemptLedger
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.deterministic import DeterministicProvider, fixture_cases
from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async


def test_storage_outage_does_not_accept(tmp_path: Path) -> None:
    """An unavailable database returns a sanitized temporary failure, never an acceptance."""
    auth, first, _ = init_demo(tmp_path)
    app = create_app(
        RuntimeConfiguration(
            Settings(), SecretStr("host=127.0.0.1 port=1 dbname=unavailable"), auth
        )
    )

    async def exercise() -> None:
        """Use a refused loopback connection to exercise the real pool timeout boundary."""
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            response = await client.post(
                "/conversations",
                json={"schema_version": 1},
                headers={
                    "Authorization": "Bearer " + first.read_text().strip(),
                    "Idempotency-Key": str(uuid4()),
                },
            )
            assert response.status_code == 503
            assert "unavailable" not in response.text or "storage_unavailable" in response.text
            assert "host=" not in response.text

    run_async(exercise())


@pytest.mark.support_db
def test_exhausted_key_is_stable(test_database_url: str) -> None:
    """Spent reservations produce one durable failure; identical retries preserve the budget."""

    async def exercise() -> None:
        """Spend both attempts before graph execution, then retry the same operation."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo, ledger = Repository(pool), AttemptLedger(pool)
            owner, key = uuid4(), uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            turn = await repo.accept(owner, parent.id, key, fixture_cases()[0].question)
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            await ledger.reserve(job, "crashed-request")
            await ledger.reserve(job, "crashed-request")
            await process_job(pool, job, Settings(), DeterministicProvider())
            repeated = await repo.accept(owner, parent.id, key, fixture_cases()[0].question)
            assert repeated.id == turn.id and repeated.status == "failed"
            assert (
                repeated.result is not None
                and repeated.result.failure_category == "attempt_exhausted"
            )

    run_async(exercise())
