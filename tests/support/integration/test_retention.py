"""Prove immediate deletion/expiry denial and eligible maintenance without resurrection."""

from uuid import uuid4

import pytest

from veritycx.persistence.database import database_pool
from veritycx.persistence.maintenance import purge_expired
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


@pytest.mark.parametrize("kind", ["delete", "expire"])
def test_retention_guard(test_database_url: str, kind: str) -> None:
    """An unfinished worker cannot write before or after maintenance removes its parent."""

    async def exercise() -> None:
        """Target only this test's conversation for maintenance, preserving unrelated rows."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            await repo.accept(owner, parent.id, uuid4(), "Question")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            assert await purge_expired(pool, target=parent.id) == 0
            if kind == "delete":
                key = uuid4()
                await repo.delete(owner, parent.id, key)
                await repo.delete(owner, parent.id, key)
            else:
                async with pool.connection() as conn:
                    await conn.execute(
                        "UPDATE support_app.conversations SET expires_at=now()-interval '1 "
                        "second' WHERE id=%s",
                        (parent.id,),
                    )
            with pytest.raises(RepositoryError, match="not_found"):
                await repo.get(owner, parent.id)
            with pytest.raises(RepositoryError, match="not_found"):
                await repo.renew(job)
            assert await purge_expired(pool, target=parent.id) == 1
            assert await purge_expired(pool, target=parent.id) == 0
            with pytest.raises(RepositoryError, match="not_found"):
                await repo.renew(job)

    run_async(exercise())


def test_purge_rollback(test_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A saver deletion failure rolls checkpoint and application removal back together."""
    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from veritycx.persistence.checkpoints import GuardedSaver

    original = AsyncPostgresSaver.adelete_thread

    async def fail_after_delete(saver: AsyncPostgresSaver, thread_id: str) -> None:
        """Inject failure after actual checkpoint deletion within the maintenance transaction."""
        await original(saver, thread_id)
        raise RuntimeError("purge_rollback")

    async def exercise() -> None:
        """Seed a real checkpoint, delete logically, fail purge then verify both stores remain."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            await repo.accept(owner, parent.id, uuid4(), "Question")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            async with pool.connection() as conn:
                saver = GuardedSaver(conn, job, "fixture")
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "schema_version": 1,
                    "conversation_id": str(parent.id),
                    "job_id": str(job.id),
                    "corpus_version": "fixture",
                }
                config: RunnableConfig = {
                    "configurable": {"thread_id": str(parent.id), "checkpoint_ns": ""}
                }
                await saver.aput(config, checkpoint, {"source": "input", "step": 0}, {})
            await repo.delete(owner, parent.id, uuid4())
            with monkeypatch.context() as patch:
                patch.setattr(AsyncPostgresSaver, "adelete_thread", fail_after_delete)
                with pytest.raises(RuntimeError, match="purge_rollback"):
                    await purge_expired(pool, target=parent.id)
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    "SELECT id FROM support_app.conversations WHERE id=%s", (parent.id,)
                )
                assert await cursor.fetchone() is not None
                cursor = await conn.execute(
                    "SELECT checkpoint_id FROM support_checkpoints.checkpoints WHERE thread_id=%s",
                    (str(parent.id),),
                )
                assert await cursor.fetchone() is not None
            assert await purge_expired(pool, target=parent.id) == 1

    run_async(exercise())
