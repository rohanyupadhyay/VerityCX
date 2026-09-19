"""Prove reserved attempts, journal reuse and deadlines survive worker takeover."""

from uuid import uuid4

import pytest

from veritycx.persistence.attempts import AttemptLedger, BudgetError
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.providers.protocol import ProviderResult
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_reservation_crash_and_fence(test_database_url: str) -> None:
    """Spent reservations survive a crashed caller; stale completions cannot overwrite them."""

    async def exercise() -> None:
        """Reserve, expire the lease, take over and prove the global cap and result reuse."""
        async with database_pool(test_database_url) as pool:
            repo, ledger = Repository(pool), AttemptLedger(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            await repo.accept(owner, parent.id, uuid4(), "Question")
            old = await repo.claim(uuid4(), conversation_id=parent.id)
            assert old is not None
            first = await ledger.reserve(old, "fixture-digest")
            assert first.ordinal == 1
            async with pool.connection() as conn:
                await conn.execute(
                    "UPDATE support_app.jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
                    (old.id,),
                )
            current = await repo.claim(uuid4(), conversation_id=parent.id)
            assert current is not None and current.fence > old.fence
            with pytest.raises(RepositoryError, match="stale_worker"):
                await ledger.save(
                    old,
                    first,
                    ProviderResult(disposition="abstain", text="No evidence", model="fixture"),
                )
            second = await ledger.reserve(current, "fixture-digest")
            assert second.ordinal == 2
            with pytest.raises(BudgetError, match="attempt_exhausted"):
                await ledger.reserve(current, "fixture-digest")
            expected = ProviderResult(disposition="abstain", text="No evidence", model="fixture")
            await ledger.save(current, second, expected)
            assert await ledger.succeeded(current, "fixture-digest") == expected
            assert await ledger.succeeded(current, "different-request") is None

    run_async(exercise())


def test_deadline_survives_takeover(test_database_url: str) -> None:
    """Elapsed wall-clock processing time cannot be reset by a fresh worker claim."""

    async def exercise() -> None:
        """Use controlled database timestamps without changing the host clock."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            turn = await repo.accept(owner, parent.id, uuid4(), "Question")
            old = await repo.claim(uuid4(), conversation_id=parent.id)
            assert old is not None
            async with pool.connection() as conn, conn.transaction():
                await conn.execute(
                    "UPDATE support_app.turns SET processing_started_at=now()-interval '61 "
                    "seconds', "
                    "deadline_at=now()-interval '1 second' WHERE id=%s",
                    (turn.id,),
                )
                await conn.execute(
                    "UPDATE support_app.jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
                    (old.id,),
                )
            current = await repo.claim(uuid4(), conversation_id=parent.id)
            assert current is not None
            with pytest.raises(BudgetError, match="timeout"):
                await AttemptLedger(pool).reserve(current, "fixture-digest")

    run_async(exercise())
