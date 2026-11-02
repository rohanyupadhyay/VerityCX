"""Journal one rewrite dispatch under the existing turn deadline and worker authority."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError, model_validator

from veritycx.conversations.models import ClosedModel
from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.retrieval import RetrievalSelection
from veritycx.knowledge.scope import CategoryCoverage, SearchScope
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
    prompt_version: Literal[1, 2]
    status: Literal["reserved", "succeeded", "failed"]
    result_json: str | None
    failure_category: str | None
    input_tokens: int | None
    output_tokens: int | None
    started_at: datetime
    ended_at: datetime | None
    selected_source_ids: list[str]
    retrieval_mode: Literal["primary", "synonym", "category", "empty"] | None
    expanded_term_count: int
    search_scope: Literal["focused", "category_overview"] | None = None
    category_keys: list[CategoryKey] | None = Field(default=None, max_length=6)
    eligible_document_count: int | None = Field(default=None, ge=0)
    represented_document_count: int | None = Field(default=None, ge=0)
    coverage_truncated: bool | None = None

    @model_validator(mode="after")
    def consistent_diagnostics(self) -> "RewriteRow":
        """Treat old unknown metadata distinctly from measured current scope."""
        coverage = (
            self.eligible_document_count,
            self.represented_document_count,
            self.coverage_truncated,
        )
        if self.search_scope is None:
            if self.category_keys is not None or any(value is not None for value in coverage):
                raise ValueError("invalid_unknown_scope")
            return self
        if self.category_keys is None:
            raise ValueError("missing_category_keys")
        SearchScope(scope=self.search_scope, categories=tuple(self.category_keys))
        if self.search_scope == "focused":
            if any(value is not None for value in coverage):
                raise ValueError("invalid_focused_coverage")
        else:
            if any(value is None for value in coverage):
                raise ValueError("missing_category_coverage")
            CategoryCoverage.model_validate(
                {
                    "eligible_document_count": self.eligible_document_count,
                    "represented_document_count": self.represented_document_count,
                    "coverage_truncated": self.coverage_truncated,
                }
            )
        return self


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
            try:
                row = RewriteRow.model_validate(raw)
            except ValidationError:
                raise RepositoryError("incompatible_state") from None
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
            context = selection.context
            scope = context.search_scope if context else None
            coverage = context.coverage if context else None
            cursor = await conn.execute(
                "UPDATE support_app.query_rewrites SET selected_source_ids=%s,retrieval_mode=%s,"
                "expanded_term_count=%s,search_scope=%s,category_keys=%s,"
                "eligible_document_count=%s,represented_document_count=%s,coverage_truncated=%s "
                "WHERE turn_id=%s AND status='succeeded' RETURNING turn_id",
                (
                    Jsonb([item.section_id for item in selection.sections]),
                    selection.mode,
                    selection.expanded_term_count,
                    scope.scope if scope else None,
                    Jsonb(list(scope.categories)) if scope else None,
                    coverage.eligible_document_count if coverage else None,
                    coverage.represented_document_count if coverage else None,
                    coverage.coverage_truncated if coverage else None,
                    job.turn_id,
                ),
            )
            if await cursor.fetchone() is None:
                raise RepositoryError("incompatible_state")
