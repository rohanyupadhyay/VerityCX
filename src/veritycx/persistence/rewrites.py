"""Journal one rewrite dispatch under the existing turn deadline and worker authority."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg.types.json import Jsonb

from veritycx.conversations.models import ClosedModel
from veritycx.knowledge.retrieval import RetrievalSelection
from veritycx.persistence.attempts import BudgetError, Reservation
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import RepositoryError, worker_guard
from veritycx.providers.rewrite import RewriteResult


class RewriteRow(ClosedModel):
    """Contain rewrite content locally under conversation retention and ownership."""

    turn_id: UUID
    request_digest: str
    model: str
    prompt_version: Literal[1]
    status: Literal["reserved", "succeeded", "failed"]
    result_json: str | None
    failure_category: str | None
    input_tokens: int | None
    output_tokens: int | None
    started_at: datetime
    ended_at: datetime | None
    selected_source_ids: list[str]
    retrieval_mode: Literal["primary", "synonym", "empty"] | None
    expanded_term_count: int


class RewriteLedger:
    """Reserve before network dispatch, reuse success, and reject uncertain replay."""

    def __init__(self, pool: DatabasePool) -> None:
        """Use the same short fenced transactions as answer-attempt bookkeeping."""
        self.pool = pool

    async def lookup(self, job: WorkJob, digest: str) -> RewriteRow | None:
        """Read only this live turn and require the exact persisted request identity."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "SELECT * FROM support_app.query_rewrites WHERE turn_id=%s", (job.turn_id,)
            )
            raw = await cursor.fetchone()
            if raw is None:
                return None
            row = RewriteRow.model_validate(raw)
            if row.request_digest != digest:
                raise RepositoryError("incompatible_state")
            return row

    async def reserve(
        self, job: WorkJob, digest: str, model: str, prompt_version: int
    ) -> Reservation:
        """Spend the sole rewrite allowance without resetting the turn deadline."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "SELECT deadline_at,clock_timestamp() AS current_time FROM support_app.turns "
                "WHERE id=%s AND status='running' FOR UPDATE",
                (job.turn_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise RepositoryError("incompatible_state")
            deadline, current = row.get("deadline_at"), row.get("current_time")
            if not isinstance(deadline, datetime) or not isinstance(current, datetime):
                raise RepositoryError("incompatible_state")
            remaining = (deadline - current).total_seconds()
            if remaining <= 0:
                raise BudgetError("timeout")
            cursor = await conn.execute(
                "SELECT turn_id FROM support_app.query_rewrites WHERE turn_id=%s", (job.turn_id,)
            )
            if await cursor.fetchone() is not None:
                raise BudgetError("rewrite_attempt_exhausted")
            await conn.execute(
                "INSERT INTO support_app.query_rewrites "
                "(turn_id,request_digest,model,prompt_version,status) "
                "VALUES (%s,%s,%s,%s,'reserved')",
                (job.turn_id, digest, model, prompt_version),
            )
            return Reservation(1, remaining)

    async def save(
        self, job: WorkJob, result: RewriteResult | None, failure: str | None = None
    ) -> None:
        """Journal validated output or a content-free failure only under the current fence."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            usage = result.usage if result else None
            cursor = await conn.execute(
                "UPDATE support_app.query_rewrites SET status=%s,result_json=%s,"
                "failure_category=%s,model=COALESCE(%s,model),input_tokens=%s,"
                "output_tokens=%s,ended_at=clock_timestamp() "
                "WHERE turn_id=%s AND status='reserved' RETURNING turn_id",
                (
                    "succeeded" if result else "failed",
                    result.model_dump_json() if result else None,
                    failure,
                    result.model if result else None,
                    usage.input_tokens if usage else None,
                    usage.output_tokens if usage else None,
                    job.turn_id,
                ),
            )
            if await cursor.fetchone() is None:
                raise RepositoryError("incompatible_state")

    async def record_retrieval(self, job: WorkJob, selection: RetrievalSelection) -> None:
        """Keep selected IDs and bounded diagnostics even when answer generation abstains."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "UPDATE support_app.query_rewrites SET selected_source_ids=%s,retrieval_mode=%s,"
                "expanded_term_count=%s WHERE turn_id=%s AND status='succeeded' RETURNING turn_id",
                (
                    Jsonb([item.section_id for item in selection.sections]),
                    selection.mode,
                    selection.expanded_term_count,
                    job.turn_id,
                ),
            )
            if await cursor.fetchone() is None:
                raise RepositoryError("incompatible_state")
