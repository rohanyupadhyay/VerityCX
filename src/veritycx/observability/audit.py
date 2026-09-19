"""Commit bounded customer results and sanitized local audit in the same fenced transaction."""

from psycopg.types.json import Jsonb

from veritycx.conversations.models import TurnResult
from veritycx.observability.export import TraceExporter, metadata
from veritycx.persistence.database import DatabaseConnection, DatabasePool, transaction
from veritycx.persistence.models import AuditEventRow, WorkJob
from veritycx.persistence.repository import worker_guard
from veritycx.providers.protocol import ProviderResult


async def commit_result(
    pool: DatabasePool,
    job: WorkJob,
    result: TurnResult,
    route: str,
    provider: ProviderResult | None = None,
) -> None:
    """Publish once while holding the parent/fence guard; never overwrite terminal results."""
    async with transaction(pool) as conn:
        await commit_result_on(conn, job, result, route, provider)


async def commit_result_on(
    conn: DatabaseConnection,
    job: WorkJob,
    result: TurnResult,
    route: str,
    provider: ProviderResult | None = None,
) -> None:
    """Publish within an existing parent transaction, including atomic escalation transitions."""
    await worker_guard(conn, job)
    cursor = await conn.execute(
        "UPDATE support_app.turns SET status=%s,result=%s "
        "WHERE id=%s AND status IN ('accepted','running') RETURNING id",
        (
            "failed" if result.kind == "error" else "completed",
            Jsonb(result.model_dump(mode="json")),
            job.turn_id,
        ),
    )
    if await cursor.fetchone() is None:
        return
    usage = provider.usage if provider else None
    await conn.execute(
        "UPDATE support_app.audit SET stage='result',outcome=%s,route=%s,source_ids=%s, "
        "failure_category=%s,model=%s,input_tokens=%s,output_tokens=%s,elapsed_ms="
        "GREATEST(0,(SELECT EXTRACT(EPOCH FROM (clock_timestamp()-created_at))*1000 "
        "FROM support_app.turns WHERE id=%s)) WHERE turn_id=%s",
        (
            result.kind,
            route,
            Jsonb([c.section_id for c in result.citations]),
            result.failure_category,
            provider.model if provider else None,
            usage.input_tokens if usage else None,
            usage.output_tokens if usage else None,
            job.turn_id,
            job.turn_id,
        ),
    )


async def export_result(
    pool: DatabasePool, job: WorkJob, exporter: TraceExporter, provider: str
) -> None:
    """Read committed local audit while the parent is live; export failure cannot alter results."""
    async with transaction(pool) as conn:
        cursor = await conn.execute(
            "SELECT a.* FROM support_app.audit a JOIN support_app.conversations c "
            "ON c.id=a.conversation_id WHERE a.turn_id=%s AND a.stage='result' "
            "AND c.status<>'deleted' AND c.expires_at>clock_timestamp()",
            (job.turn_id,),
        )
        row = await cursor.fetchone()
        event = AuditEventRow.model_validate(row) if row else None
    if event is not None:
        await exporter.send(metadata(event, provider))
