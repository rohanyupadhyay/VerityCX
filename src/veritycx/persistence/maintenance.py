"""Purge only deleted/expired parents through a deletion-only maintenance transaction."""

from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import sql

from veritycx.persistence.checkpoints import restricted_serializer
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.models import ConversationRow


async def purge_expired(pool: DatabasePool, *, target: UUID | None = None) -> int:
    """Remove eligible content atomically; preserve live parents and invalidate late writers."""
    removed = 0
    while True:
        async with transaction(pool) as conn:
            cursor = await conn.execute(
                "SELECT * FROM support_app.conversations "
                "WHERE (status='deleted' OR expires_at<=clock_timestamp()) "
                "AND (%s::uuid IS NULL OR id=%s) ORDER BY expires_at LIMIT 1 FOR UPDATE SKIP "
                "LOCKED",
                (target, target),
            )
            row = await cursor.fetchone()
            if row is None:
                break
            parent = ConversationRow.model_validate(row)
            # Maintenance does not require a live lease. It permits only deletion under this lock.
            await conn.execute(
                "UPDATE support_app.jobs SET fence=fence+1,worker_id=NULL,lease_until=NULL "
                "WHERE conversation_id=%s",
                (parent.id,),
            )
            await conn.execute(
                "UPDATE support_app.conversations SET active_job_id=NULL WHERE id=%s", (parent.id,)
            )
            await AsyncPostgresSaver(conn, serde=restricted_serializer()).adelete_thread(
                str(parent.id)
            )
            await conn.execute(
                "DELETE FROM support_app.attempts WHERE turn_id IN "
                "(SELECT id FROM support_app.turns WHERE conversation_id=%s)",
                (parent.id,),
            )
            for table in ("audit", "escalations", "operations", "jobs", "turns"):
                await conn.execute(
                    sql.SQL("DELETE FROM {} WHERE conversation_id=%s").format(
                        sql.Identifier("support_app", table)
                    ),
                    (parent.id,),
                )
            await conn.execute("DELETE FROM support_app.conversations WHERE id=%s", (parent.id,))
            removed += 1
    async with transaction(pool) as conn:
        await conn.execute(
            "DELETE FROM support_app.worker_heartbeats WHERE "
            "last_seen<clock_timestamp()-interval '1 day'"
        )
    return removed
