"""Reconcile terminal work without provider replay and retain incompatible-state evidence."""

from veritycx.conversations.models import TurnResult
from veritycx.observability.audit import commit_result
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import Repository, RepositoryError, worker_guard


async def reconcile_terminal(pool: DatabasePool, job: WorkJob) -> bool:
    """Release an unfinished normal terminal job without invoking a provider again."""
    if job.kind != "turn":
        return False
    async with transaction(pool) as conn:
        await worker_guard(conn, job)
        cursor = await conn.execute(
            "SELECT status,result->>'kind' AS kind FROM support_app.turns WHERE id=%s",
            (job.turn_id,),
        )
        row = await cursor.fetchone()
        terminal = row is not None and row.get("status") in {"completed", "failed"}
        escalation = row is not None and row.get("kind") == "escalation"
    if terminal and not escalation:
        await Repository(pool).finish(job)
        return True
    return False


async def block_incompatible(pool: DatabasePool, job: WorkJob) -> None:
    """Keep corrupt state for operator remediation and prevent new work from bypassing it."""
    try:
        await commit_result(
            pool,
            job,
            TurnResult(
                kind="error",
                text="This conversation requires operator remediation.",
                failure_category="incompatible_state",
            ),
            "blocked",
        )
        async with transaction(pool) as conn:
            await worker_guard(conn, job)
            await conn.execute(
                "UPDATE support_app.jobs SET status='failed',failure_code='incompatible_state', "
                "recovery='operator_required',fence=fence+1,worker_id=NULL,lease_until=NULL "
                "WHERE id=%s",
                (job.id,),
            )
            await conn.execute(
                "UPDATE support_app.conversations SET active_job_id=NULL,revision=revision+1 "
                "WHERE id=%s",
                (job.conversation_id,),
            )
    except RepositoryError as error:
        if str(error) not in {"not_found", "stale_worker"}:
            raise
