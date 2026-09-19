"""Reserve every provider attempt durably and journal validated output before graph progress."""

from dataclasses import dataclass
from datetime import datetime

from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.models import ProviderAttemptRow, WorkJob
from veritycx.persistence.repository import RepositoryError, worker_guard
from veritycx.providers.protocol import ProviderResult


class BudgetError(ValueError):
    """Report persisted deadline or attempt exhaustion without starting another call."""


@dataclass(frozen=True)
class Reservation:
    """Return the durably spent attempt ordinal and its remaining wall-clock budget."""

    ordinal: int
    remaining_seconds: float


class AttemptLedger:
    """Serialize reservations/results using the same live-parent worker fence."""

    def __init__(self, pool: DatabasePool) -> None:
        """Retain the verified shared pool for short ledger transactions."""
        self.pool = pool

    async def succeeded(self, job: WorkJob, digest: str) -> ProviderResult | None:
        """Reuse only validated journal output for this exact turn/request identity."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "SELECT * FROM support_app.attempts WHERE turn_id=%s "
                "AND request_digest=%s AND status='succeeded' ORDER BY ordinal LIMIT 1",
                (job.turn_id, digest),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            attempt = ProviderAttemptRow.model_validate(row)
            if attempt.result_json is None:
                raise RepositoryError("incompatible_state")
            return ProviderResult.model_validate_json(attempt.result_json)

    async def reserve(self, job: WorkJob, digest: str) -> Reservation:
        """Count a reservation before dispatch and preserve the database-time deadline."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "SELECT deadline_at,clock_timestamp() AS current_time "
                "FROM support_app.turns WHERE id=%s AND status='running' FOR UPDATE",
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
                "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                (job.turn_id,),
            )
            count_row = await cursor.fetchone()
            count = count_row.get("count") if count_row else None
            if type(count) is not int:
                raise RepositoryError("incompatible_state")
            if count >= 2:
                raise BudgetError("attempt_exhausted")
            await conn.execute(
                "INSERT INTO support_app.attempts (turn_id,ordinal,status,request_digest) "
                "VALUES (%s,%s,'reserved',%s)",
                (job.turn_id, count + 1, digest),
            )
            return Reservation(count + 1, remaining)

    async def save(
        self,
        job: WorkJob,
        reservation: Reservation,
        result: ProviderResult | None,
        failure: str | None = None,
    ) -> None:
        """Commit a validated result or sanitized error only while this fence is current."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            cursor = await conn.execute(
                "UPDATE support_app.attempts SET status=%s,result_json=%s, "
                "failure_category=%s,ended_at=clock_timestamp() WHERE turn_id=%s AND ordinal=%s "
                "AND status='reserved' RETURNING ordinal",
                (
                    "succeeded" if result else "failed",
                    result.model_dump_json() if result else None,
                    failure,
                    job.turn_id,
                    reservation.ordinal,
                ),
            )
            if await cursor.fetchone() is None:
                raise RepositoryError("incompatible_state")
