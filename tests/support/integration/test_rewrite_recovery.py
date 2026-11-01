"""Exercise real fenced rewrite reservations, recovery, and retention."""

from uuid import uuid4

import pytest

from veritycx.persistence.attempts import BudgetError
from veritycx.persistence.database import database_pool
from veritycx.persistence.maintenance import purge_expired
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.persistence.rewrites import RewriteLedger
from veritycx.providers.rewrite import RewriteResult, SearchRewrite
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_rewrite_reservation_reuse_and_independent_answer_budget(test_database_url: str) -> None:
    """Completed rewrites survive takeover and never spend answer attempts."""

    async def exercise() -> None:
        async with database_pool(test_database_url) as pool:
            repo, ledger = Repository(pool), RewriteLedger(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            turn = await repo.accept(owner, parent.id, uuid4(), "Cedar?")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            reservation = await ledger.reserve(job, "fixture", "rewrite-fixture", 1)
            assert reservation.ordinal == 1
            with pytest.raises(BudgetError, match="rewrite_attempt_exhausted"):
                await ledger.reserve(job, "fixture", "rewrite-fixture", 1)
            expected = RewriteResult(
                result=SearchRewrite(disposition="search", query="Cedar card"),
                model="rewrite-fixture",
            )
            await ledger.save(job, expected)
            saved = await ledger.lookup(job, "fixture")
            assert saved is not None and saved.result_json == expected.model_dump_json()
            with pytest.raises(RepositoryError, match="incompatible_state"):
                await ledger.lookup(job, "changed-digest")
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                        (turn.id,),
                    )
                ).fetchone()
                assert row is not None and row["count"] == 0
                await conn.execute(
                    "UPDATE support_app.jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
                    (job.id,),
                )
            current = await repo.claim(uuid4(), conversation_id=parent.id)
            assert current is not None
            restored = await ledger.lookup(current, "fixture")
            assert restored is not None and restored.status == "succeeded"
            with pytest.raises(RepositoryError, match="stale_worker"):
                await ledger.save(job, expected)
            await repo.delete(owner, parent.id, uuid4())
            assert await purge_expired(pool, target=parent.id) == 1
            async with pool.connection() as conn:
                assert (
                    await (
                        await conn.execute(
                            "SELECT turn_id FROM support_app.query_rewrites WHERE turn_id=%s",
                            (turn.id,),
                        )
                    ).fetchone()
                    is None
                )

    run_async(exercise())


def test_rewrite_deadline_and_spent_uncertain_reservation(test_database_url: str) -> None:
    """A reserved external call is not replayed when its result was lost."""
    from veritycx.providers.rewrite import DeterministicQueryRewriter, RewriteRequest
    from veritycx.providers.rewrite_execution import invoke_rewriter

    async def exercise() -> None:
        async with database_pool(test_database_url) as pool:
            repo, ledger = Repository(pool), RewriteLedger(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            turn = await repo.accept(owner, parent.id, uuid4(), "Cedar?")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            await ledger.reserve(job, "uncertain", "fixture", 1)
            request = RewriteRequest(
                question="Cedar?",
                correlation_id="fixture",
                corpus_version="fixture",
                remaining_seconds=10.0,
            )
            with pytest.raises(RepositoryError, match="incompatible_state"):
                await invoke_rewriter(DeterministicQueryRewriter(), ledger, job, request, "fixture")
            async with pool.connection() as conn:
                await conn.execute(
                    "UPDATE support_app.turns SET "
                    "processing_started_at=now()-interval '61 seconds',"
                    "deadline_at=now()-interval '1 second' WHERE id=%s",
                    (turn.id,),
                )
            with pytest.raises(BudgetError, match="timeout"):
                await ledger.reserve(job, "uncertain", "fixture", 1)

    run_async(exercise())
