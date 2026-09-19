"""Persist idempotent pauses and consume them into fenced, provider-free resume jobs."""

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from veritycx.conversations.lifecycle import ACKNOWLEDGMENT, escalation_summary
from veritycx.conversations.models import ResumeInput, TurnResult
from veritycx.observability.audit import commit_result_on
from veritycx.persistence.database import DatabaseConnection, DatabasePool, transaction
from veritycx.persistence.models import ConversationRow, EscalationRow, TurnRow, WorkJob
from veritycx.persistence.repository import (
    RepositoryError,
    insert_operation,
    key_lock,
    live_parent,
    operation,
    request_digest,
    worker_guard,
)


async def ensure_pause(pool: DatabasePool, job: WorkJob) -> EscalationRow:
    """Commit pending escalation, truthful result and audit before advancing to interrupt."""
    async with transaction(pool) as conn:
        await worker_guard(conn, job)
        cursor = await conn.execute(
            "SELECT * FROM support_app.escalations WHERE conversation_id=%s AND status='pending'",
            (job.conversation_id,),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            return EscalationRow.model_validate(existing)
        cursor = await conn.execute(
            "SELECT * FROM support_app.turns WHERE conversation_id=%s ORDER BY sequence",
            (job.conversation_id,),
        )
        turns = [TurnRow.model_validate(row) for row in await cursor.fetchall()]
        sources = sorted(
            {
                citation.section_id
                for turn in turns
                if turn.result
                for citation in turn.result.citations
            }
        )
        cursor = await conn.execute(
            "INSERT INTO support_app.escalations "
            "(id,conversation_id,triggering_turn_id,reason,summary,source_ids,pause_id,status) "
            "VALUES (%s,%s,%s,'customer_requested',%s,%s,%s,'pending') RETURNING *",
            (
                uuid4(),
                job.conversation_id,
                job.turn_id,
                escalation_summary([turn.text for turn in turns]),
                Jsonb(sources),
                uuid4(),
            ),
        )
        pause = EscalationRow.model_validate(await cursor.fetchone())
        await conn.execute(
            "UPDATE support_app.conversations SET "
            "status='escalation_pending',revision=revision+1 WHERE id=%s",
            (job.conversation_id,),
        )
        await commit_result_on(
            conn, job, TurnResult(kind="escalation", text=ACKNOWLEDGMENT), "human"
        )
        return pause


async def accept_paused(
    conn: DatabaseConnection, parent: ConversationRow, key: UUID, message: str, digest: str
) -> TurnRow:
    """Save a context-only message without creating a job or invoking a specialist."""
    cursor = await conn.execute(
        "SELECT * FROM support_app.escalations WHERE conversation_id=%s AND "
        "status='pending' FOR UPDATE",
        (parent.id,),
    )
    pause = EscalationRow.model_validate(await cursor.fetchone())
    turn_id = uuid4()
    result = TurnResult(kind="escalation", text=ACKNOWLEDGMENT)
    cursor = await conn.execute(
        "INSERT INTO support_app.turns "
        "(id,conversation_id,sequence,request_key,text,status,result) "
        "VALUES (%s,%s,%s,%s,%s,'completed',%s) RETURNING *",
        (
            turn_id,
            parent.id,
            parent.customer_count + 1,
            key,
            message,
            Jsonb(result.model_dump(mode="json")),
        ),
    )
    turn = TurnRow.model_validate(await cursor.fetchone())
    await conn.execute(
        "UPDATE support_app.escalations SET summary=%s WHERE id=%s",
        (escalation_summary([pause.summary, message]), pause.id),
    )
    await conn.execute(
        "UPDATE support_app.conversations SET customer_count=customer_count+1,revision=revision+1, "
        "activity_at=clock_timestamp(),expires_at=clock_timestamp()+interval '30 days' WHERE id=%s",
        (parent.id,),
    )
    await conn.execute(
        "INSERT INTO support_app.audit "
        "(id,conversation_id,turn_id,correlation_id,stage,outcome,route) "
        "VALUES (%s,%s,%s,%s,'result','escalation','paused')",
        (uuid4(), parent.id, turn_id, uuid4()),
    )
    await insert_operation(conn, parent.owner_id, key, "turn", parent.id, digest, turn_id)
    return turn


async def resume(
    pool: DatabasePool, owner: UUID, target: UUID, key: UUID, value: ResumeInput
) -> WorkJob:
    """Consume the current owner-authorized pause once and durably queue a control job."""
    digest = request_digest("resume", target, value.model_dump())
    async with transaction(pool) as conn:
        await key_lock(conn, owner, key)
        parent = await live_parent(conn, target, owner)
        previous = await operation(conn, owner, key, digest)
        if previous is not None:
            cursor = await conn.execute(
                "SELECT * FROM support_app.jobs WHERE id=%s", (previous.resource_id,)
            )
            return WorkJob.model_validate(await cursor.fetchone())
        blocked = await conn.execute(
            "SELECT id FROM support_app.jobs WHERE conversation_id=%s AND "
            "failure_code='incompatible_state' LIMIT 1",
            (target,),
        )
        if await blocked.fetchone() is not None:
            raise RepositoryError("incompatible_state")
        if parent.active_job_id is not None:
            raise RepositoryError("busy")
        if parent.status != "escalation_pending" or parent.revision != value.expected_revision:
            raise RepositoryError("stale_resume")
        cursor = await conn.execute(
            "SELECT * FROM support_app.escalations WHERE conversation_id=%s "
            "AND pause_id=%s AND status='pending' FOR UPDATE",
            (target, UUID(value.pause_id)),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RepositoryError("stale_resume")
        pause = EscalationRow.model_validate(row)
        cursor = await conn.execute(
            "SELECT * FROM support_app.jobs WHERE turn_id=%s AND kind='turn' ORDER "
            "BY created_at LIMIT 1",
            (pause.triggering_turn_id,),
        )
        origin = WorkJob.model_validate(await cursor.fetchone())
        job_id = uuid4()
        cursor = await conn.execute(
            "INSERT INTO support_app.jobs "
            "(id,conversation_id,turn_id,kind,status,checkpoint_id) VALUES "
            "(%s,%s,%s,'resume','accepted',%s) RETURNING *",
            (
                job_id,
                target,
                pause.triggering_turn_id,
                origin.checkpoint_id if pause.reason != "resume_retry" else None,
            ),
        )
        job = WorkJob.model_validate(await cursor.fetchone())
        await conn.execute(
            "UPDATE support_app.escalations SET status='cancelled',consumed_at=clock_timestamp(), "
            "consumed_operation_id=%s WHERE id=%s",
            (key, pause.id),
        )
        await insert_operation(conn, owner, key, "resume", target, digest, job_id)
        await conn.execute(
            "UPDATE support_app.conversations SET active_job_id=%s,revision=revision+1 WHERE id=%s",
            (job_id, target),
        )
        return job


async def consumed_pause(pool: DatabasePool, job: WorkJob) -> tuple[EscalationRow, UUID]:
    """Recover only the pause consumed by this durable resume operation and its original job."""
    async with transaction(pool) as conn:
        parent = await worker_guard(conn, job)
        cursor = await conn.execute(
            "SELECT e.* FROM support_app.escalations e JOIN support_app.operations o "
            "ON o.request_key=e.consumed_operation_id AND o.owner_id=%s "
            "WHERE o.resource_id=%s AND o.kind='resume' AND e.conversation_id=%s AND "
            "e.status='cancelled'",
            (parent.owner_id, job.id, job.conversation_id),
        )
        pause = EscalationRow.model_validate(await cursor.fetchone())
        cursor = await conn.execute(
            "SELECT id FROM support_app.jobs WHERE turn_id=%s AND kind='turn' ORDER "
            "BY created_at LIMIT 1",
            (pause.triggering_turn_id,),
        )
        row = await cursor.fetchone()
        origin = row.get("id") if row else None
        if not isinstance(origin, UUID):
            raise RepositoryError("incompatible_state")
        return pause, origin


async def finalize_resume(pool: DatabasePool, job: WorkJob) -> None:
    """Atomically reactivate after trusted graph continuation, without adding a customer turn."""
    async with transaction(pool) as conn:
        await worker_guard(conn, job)
        await conn.execute(
            "UPDATE support_app.jobs SET "
            "status='completed',worker_id=NULL,lease_until=NULL "
            "WHERE id=%s",
            (job.id,),
        )
        await conn.execute(
            "UPDATE support_app.conversations SET "
            "status='active',active_job_id=NULL,revision=revision+1, "
            "activity_at=clock_timestamp(),expires_at=clock_timestamp()+interval '30 "
            "days' WHERE id=%s",
            (job.conversation_id,),
        )


async def fail_resume(pool: DatabasePool, job: WorkJob) -> None:
    """Fence a compatible failed control job and atomically issue a new consent pause."""
    pause, _ = await consumed_pause(pool, job)
    async with transaction(pool) as conn:
        await worker_guard(conn, job)
        await conn.execute(
            "UPDATE support_app.jobs SET status='failed',failure_code='control_failed', "
            "recovery='retry_with_new_pause',fence=fence+1,worker_id=NULL,lease_until=NULL "
            "WHERE id=%s",
            (job.id,),
        )
        await conn.execute(
            "INSERT INTO support_app.escalations "
            "(id,conversation_id,triggering_turn_id,reason,summary,source_ids,pause_id,status) "
            "VALUES (%s,%s,%s,'resume_retry',%s,%s,%s,'pending')",
            (
                uuid4(),
                job.conversation_id,
                pause.triggering_turn_id,
                pause.summary,
                Jsonb(pause.source_ids),
                uuid4(),
            ),
        )
        await conn.execute(
            "UPDATE support_app.conversations SET active_job_id=NULL,revision=revision+1 "
            "WHERE id=%s",
            (job.conversation_id,),
        )
