"""Persist truthful pauses and context-only follow-up messages without provider execution."""

from uuid import uuid4

import pytest

from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_pause_and_context(test_database_url: str) -> None:
    """Requesting a human creates one durable pause; subsequent messages only update context."""

    async def exercise() -> None:
        """Run the actual interrupt graph and inspect its authoritative state."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner, key = uuid4(), uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            first = await repo.accept(owner, parent.id, key, "I want a human agent")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            await process_job(pool, job, Settings(), DeterministicProvider())
            assert (await repo.get(owner, parent.id)).status == "escalation_pending"
            assert (await repo.accept(owner, parent.id, key, "I want a human agent")).id == first.id
            paused = await repo.accept(
                owner, parent.id, uuid4(), "Please retain this additional context"
            )
            assert paused.status == "completed" and paused.result is not None
            assert "nobody has been notified" in paused.result.text.lower()
            assert await repo.claim(uuid4(), conversation_id=parent.id) is None
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT summary FROM support_app.escalations WHERE conversation_id=%s "
                    "AND status='pending'",
                    (parent.id,),
                )
                row = await cursor.fetchone()
                assert row and "additional context" in str(row["summary"])
                cursor = await conn.execute(
                    "SELECT count(*) AS total FROM support_app.attempts WHERE turn_id IN "
                    "(SELECT id FROM support_app.turns WHERE conversation_id=%s)",
                    (parent.id,),
                )
                row = await cursor.fetchone()
                assert row and row["total"] == 0

    run_async(exercise())
