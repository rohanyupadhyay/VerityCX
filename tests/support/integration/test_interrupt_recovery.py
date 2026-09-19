"""Recover a durably consumed pause exactly once, retaining the latest paused history."""

from uuid import uuid4

import pytest

from veritycx.conversations.models import ResumeInput
from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.escalations import ensure_pause, fail_resume, resume
from veritycx.persistence.models import EscalationRow
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


@pytest.mark.parametrize("missing_interrupt", [False, True])
@pytest.mark.parametrize("terminal_failure", [False, True])
def test_consumed_resume_recovery(
    test_database_url: str, missing_interrupt: bool, terminal_failure: bool
) -> None:
    """Accept a resume, abandon the caller, then recover from its durable control job."""

    async def exercise() -> None:
        """Assert one transition, stable duplicate operation and stale-pause rejection."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            await repo.accept(owner, parent.id, uuid4(), "I want a human agent")
            initial = await repo.claim(uuid4(), conversation_id=parent.id)
            assert initial is not None
            if missing_interrupt:
                await ensure_pause(pool, initial)
                async with pool.connection() as conn:
                    await conn.execute(
                        "UPDATE support_app.jobs SET "
                        "lease_until=clock_timestamp()-interval '1 second' "
                        "WHERE id=%s",
                        (initial.id,),
                    )
                reclaimed = await repo.claim(uuid4(), conversation_id=parent.id)
                assert reclaimed is not None and reclaimed.id == initial.id
                await process_job(pool, reclaimed, Settings(), DeterministicProvider())
            else:
                await process_job(pool, initial, Settings(), DeterministicProvider())
            await repo.accept(owner, parent.id, uuid4(), "Additional context")
            current = await repo.get(owner, parent.id)
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT * FROM support_app.escalations WHERE conversation_id=%s "
                    "AND status='pending'",
                    (parent.id,),
                )
                pause = EscalationRow.model_validate(await cursor.fetchone())
            value = ResumeInput(
                pause_id=str(pause.pause_id),
                expected_revision=current.revision,
                continue_automation=True,
            )
            key = uuid4()
            accepted = await resume(pool, owner, parent.id, key, value)
            assert (await resume(pool, owner, parent.id, key, value)).id == accepted.id
            with pytest.raises(RepositoryError):
                await resume(pool, uuid4(), parent.id, uuid4(), value)
            claimed = await repo.claim(uuid4(), conversation_id=parent.id)
            assert claimed is not None
            if terminal_failure:
                await fail_resume(pool, claimed)
                assert (await resume(pool, owner, parent.id, key, value)).status == "failed"
                with pytest.raises(RepositoryError, match="stale_worker"):
                    await repo.renew(claimed)
                async with pool.connection() as conn:
                    cursor = await conn.execute(
                        "SELECT * FROM support_app.escalations WHERE conversation_id=%s "
                        "AND status='pending'",
                        (parent.id,),
                    )
                    fresh = EscalationRow.model_validate(await cursor.fetchone())
                assert fresh.pause_id != pause.pause_id
                current = await repo.get(owner, parent.id)
                value = ResumeInput(
                    pause_id=str(fresh.pause_id),
                    expected_revision=current.revision,
                    continue_automation=True,
                )
                key = uuid4()
                await resume(pool, owner, parent.id, key, value)
                claimed = await repo.claim(uuid4(), conversation_id=parent.id)
                assert claimed is not None
            await process_job(pool, claimed, Settings(), DeterministicProvider())
            assert (await repo.get(owner, parent.id)).status == "active"
            assert (await resume(pool, owner, parent.id, key, value)).status == "completed"
            with pytest.raises(RepositoryError, match="stale_resume"):
                await resume(pool, owner, parent.id, uuid4(), value)

    run_async(exercise())
