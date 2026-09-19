"""Prove owner-scoped idempotency, atomic acceptance, concurrency and fenced claims."""

import asyncio
from uuid import UUID, uuid4

import pytest

from veritycx.persistence.database import DatabaseConnection, database_pool
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_acceptance_and_claim(test_database_url: str) -> None:
    """Exercise actual rows, one active job and immutable processing deadlines."""

    async def exercise() -> None:
        """Run a scoped conversation through acceptance, duplicate and claim paths."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner, key = uuid4(), uuid4()
            conversation = await repo.create(owner, key, "synthetic-v1")
            assert (await repo.create(owner, key, "synthetic-v1")).id == conversation.id
            with pytest.raises(RepositoryError, match="idempotency_conflict"):
                await repo.create(owner, key, "different-corpus")
            with pytest.raises(RepositoryError, match="not_found"):
                await repo.get(uuid4(), conversation.id)
            turn_key = uuid4()
            turn = await repo.accept(owner, conversation.id, turn_key, "Synthetic question")
            assert (
                await repo.accept(owner, conversation.id, turn_key, "Synthetic question")
            ).id == turn.id
            with pytest.raises(RepositoryError, match="idempotency_conflict"):
                await repo.accept(owner, conversation.id, turn_key, "Different question")
            with pytest.raises(RepositoryError, match="busy"):
                await repo.accept(owner, conversation.id, uuid4(), "Another question")
            job = await repo.claim(uuid4(), conversation_id=conversation.id)
            assert job is not None and job.fence == 1
            assert await repo.claim(uuid4(), conversation_id=conversation.id) is None
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT deadline_at-processing_started_at AS budget "
                    "FROM support_app.turns WHERE id=%s",
                    (turn.id,),
                )
                row = await cursor.fetchone()
                assert row is not None and str(row["budget"]) == "0:01:00"
                cursor = await conn.execute(
                    "SELECT count(*) AS count FROM support_app.audit WHERE turn_id=%s", (turn.id,)
                )
                row = await cursor.fetchone()
                assert row is not None and row["count"] == 1
                await conn.execute(
                    "UPDATE support_app.jobs SET lease_until=clock_timestamp()-interval '1 "
                    "second' WHERE id=%s",
                    (job.id,),
                )
            takeover = await repo.claim(uuid4(), conversation_id=conversation.id)
            assert takeover is not None and takeover.fence == 2
            with pytest.raises(RepositoryError, match="stale_worker"):
                await repo.renew(job)
            await repo.renew(takeover)

    run_async(exercise())


def test_concurrent_acceptance(test_database_url: str) -> None:
    """Distinct simultaneous messages cannot silently overwrite accepted work."""

    async def exercise() -> None:
        """Race two transactions against the same live parent."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            conversation = await repo.create(owner, uuid4(), "synthetic-v1")
            results = await asyncio.gather(
                repo.accept(owner, conversation.id, uuid4(), "one"),
                repo.accept(owner, conversation.id, uuid4(), "two"),
                return_exceptions=True,
            )
            assert sum(isinstance(item, RepositoryError) for item in results) == 1
            assert (await repo.get(owner, conversation.id)).customer_count == 1

    run_async(exercise())


def test_limit_and_atomic_rollback(test_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject over-limit writes and prove a failed operation insert rolls back the turn/audit."""

    async def exercise() -> None:
        """Inject a final acceptance failure, then exercise the 100th-message boundary."""
        from veritycx.persistence import repository

        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")

            async def fail_insert(
                conn: DatabaseConnection,
                owner: UUID,
                key: UUID,
                kind: str,
                conversation_id: UUID,
                digest: str,
                resource_id: UUID,
            ) -> None:
                """Fail the last acceptance write to expose partial-commit defects."""
                raise RuntimeError("injected_acceptance_failure")

            with monkeypatch.context() as patch:
                patch.setattr(repository, "insert_operation", fail_insert)
                with pytest.raises(RuntimeError, match="injected_acceptance_failure"):
                    await repo.accept(owner, parent.id, uuid4(), "Question")
            assert (await repo.get(owner, parent.id)).customer_count == 0
            async with pool.connection() as conn:
                await conn.execute(
                    "UPDATE support_app.conversations SET customer_count=99 WHERE id=%s",
                    (parent.id,),
                )
            key = uuid4()
            hundred = await repo.accept(owner, parent.id, key, "x" * 8000)
            assert hundred.sequence == 100
            assert (await repo.accept(owner, parent.id, key, "x" * 8000)).id == hundred.id
            async with pool.connection() as conn, conn.transaction():
                await conn.execute(
                    "UPDATE support_app.jobs SET status='completed' WHERE conversation_id=%s",
                    (parent.id,),
                )
                await conn.execute(
                    "UPDATE support_app.conversations SET active_job_id=NULL WHERE id=%s",
                    (parent.id,),
                )
            with pytest.raises(RepositoryError, match="conversation_limit"):
                await repo.accept(owner, parent.id, uuid4(), "excess")

    run_async(exercise())
