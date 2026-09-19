"""Prove saver writes and application pointers share the actual guard transaction."""

from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import empty_checkpoint

from veritycx.persistence.checkpoints import GuardedSaver
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_checkpoint_rollback_and_fence(test_database_url: str) -> None:
    """Rollback checkpoints, blobs, pending writes and pointer then reject late workers."""

    async def exercise() -> None:
        """Execute native saver calls under a borrowed connection and outer transaction."""
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
                    "evidence_ids": ["synthetic"],
                }
                checkpoint["channel_versions"] = {key: 1 for key in checkpoint["channel_values"]}
                config: RunnableConfig = {
                    "configurable": {"thread_id": str(parent.id), "checkpoint_ns": ""}
                }
                with pytest.raises(RuntimeError, match="rollback_probe"):
                    async with conn.transaction():
                        saved = await saver.aput(
                            config,
                            checkpoint,
                            {"source": "input", "step": 0},
                            checkpoint["channel_versions"],
                        )
                        await saver.aput_writes(saved, [("route", "knowledge")], "task")
                        raise RuntimeError("rollback_probe")
                for table in ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]:
                    from psycopg import sql

                    cursor = await conn.execute(
                        sql.SQL("SELECT count(*) AS count FROM {} WHERE thread_id=%s").format(
                            sql.Identifier("support_checkpoints", table)
                        ),
                        (str(parent.id),),
                    )
                    row = await cursor.fetchone()
                    assert row is not None and row["count"] == 0
                cursor = await conn.execute(
                    "SELECT checkpoint_id FROM support_app.jobs WHERE id=%s", (job.id,)
                )
                row = await cursor.fetchone()
                assert row is not None and row["checkpoint_id"] is None
                saved = await saver.aput(
                    config,
                    checkpoint,
                    {"source": "input", "step": 0},
                    checkpoint["channel_versions"],
                )
                assert await saver.aget_tuple(saved) is not None
                await conn.execute(
                    "UPDATE support_app.jobs SET fence=fence+1 WHERE id=%s", (job.id,)
                )
                with pytest.raises(RepositoryError, match="stale_worker"):
                    await saver.aput_writes(saved, [("route", "knowledge")], "late")
                await conn.execute(
                    "UPDATE support_app.conversations SET status='deleted' WHERE id=%s",
                    (parent.id,),
                )
                with pytest.raises(RepositoryError, match="not_found"):
                    await saver.aput(config, checkpoint, {"source": "input", "step": 0}, {})

    run_async(exercise())


@pytest.mark.parametrize("parent_state", ["expired", "absent"])
def test_unavailable_parent(test_database_url: str, parent_state: str) -> None:
    """Delayed saver writes must not recreate physically absent or expired parents."""

    async def exercise() -> None:
        """Change only this test's parent before attempting a fenced saver write."""
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), "fixture")
            await repo.accept(owner, parent.id, uuid4(), "Question")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            async with pool.connection() as conn:
                if parent_state == "expired":
                    await conn.execute(
                        "UPDATE support_app.conversations SET "
                        "expires_at=now()-interval '1 second' WHERE id=%s",
                        (parent.id,),
                    )
                else:
                    async with conn.transaction():
                        await conn.execute(
                            "UPDATE support_app.conversations SET active_job_id=NULL WHERE id=%s",
                            (parent.id,),
                        )
                        for table in ["audit", "jobs", "operations", "turns"]:
                            from psycopg import sql

                            await conn.execute(
                                sql.SQL("DELETE FROM {} WHERE conversation_id=%s").format(
                                    sql.Identifier("support_app", table)
                                ),
                                (parent.id,),
                            )
                        await conn.execute(
                            "DELETE FROM support_app.conversations WHERE id=%s", (parent.id,)
                        )
                saver = GuardedSaver(conn, job, "fixture")
                config: RunnableConfig = {
                    "configurable": {
                        "thread_id": str(parent.id),
                        "checkpoint_ns": "",
                        "checkpoint_id": "late",
                    }
                }
                with pytest.raises(RepositoryError, match="not_found"):
                    await saver.aput_writes(config, [("route", "knowledge")], "late")

    run_async(exercise())
