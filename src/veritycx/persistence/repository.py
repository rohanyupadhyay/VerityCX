"""Serialize durable acceptance and worker authority using short parent-first transactions."""

import json
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from veritycx.conversations.models import TurnInput
from veritycx.persistence.database import DatabaseConnection, DatabasePool, transaction
from veritycx.persistence.models import ConversationRow, OperationRow, TurnRow, WorkJob


class RepositoryError(ValueError):
    """Carry a safe domain category without database diagnostics or customer content."""


def request_digest(kind: str, target: UUID | None, body: dict[str, object]) -> str:
    """Hash a canonical semantic request with explicit operation and target binding."""
    payload = json.dumps(
        {"kind": kind, "target": str(target) if target else None, "body": body},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(payload.encode()).hexdigest()


async def key_lock(conn: DatabaseConnection, owner: UUID, key: UUID) -> None:
    """Serialize duplicate acceptance even before a conversation row exists."""
    lock = int.from_bytes(sha256(owner.bytes + key.bytes).digest()[:8], signed=True)
    await conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock,))


async def live_parent(
    conn: DatabaseConnection, conversation_id: UUID, owner: UUID | None = None
) -> ConversationRow:
    """Lock an existing live parent, optionally requiring an authenticated owner."""
    cursor = await conn.execute(
        "SELECT * FROM support_app.conversations WHERE id=%s AND status<>'deleted' "
        "AND expires_at>clock_timestamp() AND (%s::uuid IS NULL OR owner_id=%s) FOR UPDATE",
        (conversation_id, owner, owner),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RepositoryError("not_found")
    return ConversationRow.model_validate(row)


async def operation(
    conn: DatabaseConnection, owner: UUID, key: UUID, digest: str
) -> OperationRow | None:
    """Return the original operation or reject a conflicting use of the key."""
    cursor = await conn.execute(
        "SELECT * FROM support_app.operations WHERE owner_id=%s AND request_key=%s", (owner, key)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    result = OperationRow.model_validate(row)
    if result.request_digest != digest:
        raise RepositoryError("idempotency_conflict")
    return result


async def insert_operation(
    conn: DatabaseConnection,
    owner: UUID,
    key: UUID,
    kind: str,
    conversation_id: UUID,
    digest: str,
    resource_id: UUID,
) -> None:
    """Record idempotency within the same transaction as the accepted effect."""
    await conn.execute(
        "INSERT INTO support_app.operations "
        "(owner_id,request_key,kind,conversation_id,request_digest,resource_id) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (owner, key, kind, conversation_id, digest, resource_id),
    )


async def worker_guard(conn: DatabaseConnection, job: WorkJob) -> ConversationRow:
    """Lock parent then job and reject obsolete, expired or replaced workers."""
    parent = await live_parent(conn, job.conversation_id)
    cursor = await conn.execute(
        "SELECT id FROM support_app.jobs WHERE id=%s AND conversation_id=%s "
        "AND status='running' AND worker_id=%s AND fence=%s AND lease_until>clock_timestamp() "
        "FOR UPDATE",
        (job.id, job.conversation_id, job.worker_id, job.fence),
    )
    if parent.active_job_id != job.id or job.worker_id is None or await cursor.fetchone() is None:
        raise RepositoryError("stale_worker")
    return parent


class Repository:
    """Expose atomic identity/acceptance/claim primitives over a verified bounded pool."""

    def __init__(self, pool: DatabasePool) -> None:
        """Retain the shared pool; no connection or lock survives a method call."""
        self.pool = pool

    async def create(self, owner: UUID, key: UUID, corpus: str) -> ConversationRow:
        """Create once per owner/key, binding retries to the configured corpus."""
        digest = request_digest("create", None, {"corpus": corpus})
        async with transaction(self.pool) as conn:
            await key_lock(conn, owner, key)
            previous = await operation(conn, owner, key, digest)
            if previous is not None:
                return await live_parent(conn, previous.conversation_id, owner)
            conversation_id = uuid4()
            cursor = await conn.execute(
                "INSERT INTO support_app.conversations "
                "(id,owner_id,corpus_version,expires_at) VALUES "
                "(%s,%s,%s,clock_timestamp()+interval '30 days') "
                "RETURNING *",
                (conversation_id, owner, corpus),
            )
            row = await cursor.fetchone()
            result = ConversationRow.model_validate(row)
            await insert_operation(
                conn, owner, key, "create", conversation_id, digest, conversation_id
            )
            return result

    async def get(self, owner: UUID, conversation_id: UUID) -> ConversationRow:
        """Read only authorized live metadata without refreshing its expiry."""
        async with transaction(self.pool) as conn:
            return await live_parent(conn, conversation_id, owner)

    async def accept(self, owner: UUID, conversation_id: UUID, key: UUID, message: str) -> TurnRow:
        """Commit message/job/audit/key together; duplicate checks precede busy/count limits."""
        TurnInput(message=message)
        digest = request_digest("turn", conversation_id, {"message": message})
        async with transaction(self.pool) as conn:
            await key_lock(conn, owner, key)
            parent = await live_parent(conn, conversation_id, owner)
            previous = await operation(conn, owner, key, digest)
            if previous is not None:
                cursor = await conn.execute(
                    "SELECT * FROM support_app.turns WHERE id=%s AND conversation_id=%s",
                    (previous.resource_id, conversation_id),
                )
                return TurnRow.model_validate(await cursor.fetchone())
            blocked = await conn.execute(
                "SELECT id FROM support_app.jobs WHERE conversation_id=%s "
                "AND failure_code='incompatible_state' LIMIT 1",
                (conversation_id,),
            )
            if await blocked.fetchone() is not None:
                raise RepositoryError("incompatible_state")
            if parent.active_job_id is not None:
                raise RepositoryError("busy")
            if parent.customer_count >= 100:
                raise RepositoryError("conversation_limit")
            if parent.status == "escalation_pending":
                from veritycx.persistence.escalations import accept_paused

                return await accept_paused(conn, parent, key, message, digest)
            if parent.status != "active":
                raise RepositoryError("incompatible_state")
            turn_id, job_id = uuid4(), uuid4()
            cursor = await conn.execute(
                "INSERT INTO support_app.turns "
                "(id,conversation_id,sequence,request_key,text,status) VALUES "
                "(%s,%s,%s,%s,%s,'accepted') RETURNING *",
                (turn_id, conversation_id, parent.customer_count + 1, key, message),
            )
            turn = TurnRow.model_validate(await cursor.fetchone())
            await conn.execute(
                "INSERT INTO support_app.jobs (id,conversation_id,turn_id,kind,status) "
                "VALUES (%s,%s,%s,'turn','accepted')",
                (job_id, conversation_id, turn_id),
            )
            await conn.execute(
                "UPDATE support_app.conversations SET "
                "active_job_id=%s,customer_count=customer_count+1, "
                "revision=revision+1,activity_at=clock_timestamp(),expires_at=clock_timestamp()+interval"
                " '30 days' WHERE id=%s",
                (job_id, conversation_id),
            )
            await conn.execute(
                "INSERT INTO support_app.audit "
                "(id,conversation_id,turn_id,correlation_id,stage,outcome,route) "
                "VALUES (%s,%s,%s,%s,'acceptance','accepted','pending')",
                (uuid4(), conversation_id, turn_id, uuid4()),
            )
            await insert_operation(conn, owner, key, "turn", conversation_id, digest, turn_id)
            return turn

    async def claim(self, worker: UUID, *, conversation_id: UUID | None = None) -> WorkJob | None:
        """Take one eligible job under its parent lock, preserving its first-claim deadline."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT c.id FROM support_app.conversations c "
                "JOIN support_app.jobs j ON j.id=c.active_job_id "
                "WHERE c.status<>'deleted' AND c.expires_at>clock_timestamp() "
                "AND (j.status='accepted' OR (j.status='running' AND "
                "j.lease_until<=clock_timestamp())) "
                "AND (%s::uuid IS NULL OR c.id=%s) ORDER BY j.created_at LIMIT 1 FOR UPDATE OF "
                "c SKIP LOCKED",
                (conversation_id, conversation_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            candidate = row.get("id")
            if not isinstance(candidate, UUID):
                raise RepositoryError("incompatible_state")
            cursor = await conn.execute(
                "UPDATE support_app.jobs SET status='running',worker_id=%s,fence=fence+1, "
                "lease_until=clock_timestamp()+interval '30 seconds' WHERE conversation_id=%s "
                "AND status IN ('accepted','running') RETURNING *",
                (worker, candidate),
            )
            job = WorkJob.model_validate(await cursor.fetchone())
            if job.turn_id is not None:
                await conn.execute(
                    "UPDATE support_app.turns SET status='running',processing_started_at=now(), "
                    "deadline_at=now()+interval '60 seconds' WHERE id=%s AND "
                    "processing_started_at IS NULL "
                    "AND status IN ('accepted','running')",
                    (job.turn_id,),
                )
            return job

    async def renew(self, job: WorkJob) -> None:
        """Refresh only a still-valid lease; never revive expired worker authority."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            await conn.execute(
                "UPDATE support_app.jobs SET lease_until=clock_timestamp()+interval '30 seconds' "
                "WHERE id=%s",
                (job.id,),
            )

    async def heartbeat(self, worker: UUID) -> None:
        """Publish content-free liveness for the service readiness check."""
        async with transaction(self.pool) as conn:
            await conn.execute(
                "INSERT INTO support_app.worker_heartbeats VALUES (%s,clock_timestamp()) "
                "ON CONFLICT (worker_id) DO UPDATE SET last_seen=EXCLUDED.last_seen",
                (worker,),
            )

    async def finish(
        self, job: WorkJob, status: Literal["completed", "failed"] = "completed"
    ) -> None:
        """Release one fenced job only after its caller reconciles durable terminal state."""
        async with transaction(self.pool) as conn:
            await worker_guard(conn, job)
            if job.turn_id is not None:
                cursor = await conn.execute(
                    "SELECT status FROM support_app.turns WHERE id=%s FOR UPDATE", (job.turn_id,)
                )
                row = await cursor.fetchone()
                if row is None or row.get("status") not in {"completed", "failed"}:
                    raise RepositoryError("incompatible_state")
            await conn.execute(
                "UPDATE support_app.jobs SET status=%s,worker_id=NULL,lease_until=NULL WHERE id=%s",
                (status, job.id),
            )
            await conn.execute(
                "UPDATE support_app.conversations SET active_job_id=NULL,revision=revision+1 "
                "WHERE id=%s",
                (job.conversation_id,),
            )

    async def delete(self, owner: UUID, conversation_id: UUID, key: UUID) -> None:
        """Revoke access and acknowledge only retained, owner-authorized identical retries."""
        digest = request_digest("delete", conversation_id, {})
        async with transaction(self.pool) as conn:
            await key_lock(conn, owner, key)
            cursor = await conn.execute(
                "SELECT * FROM support_app.conversations WHERE id=%s AND owner_id=%s FOR UPDATE",
                (conversation_id, owner),
            )
            row = await cursor.fetchone()
            if row is None:
                raise RepositoryError("not_found")
            previous = await operation(conn, owner, key, digest)
            if previous is not None:
                return
            await live_parent(conn, conversation_id, owner)
            await conn.execute(
                "UPDATE support_app.jobs SET fence=fence+1,worker_id=NULL,lease_until=NULL "
                "WHERE conversation_id=%s",
                (conversation_id,),
            )
            await conn.execute(
                "UPDATE support_app.conversations SET "
                "status='deleted',deleted_at=clock_timestamp(), "
                "revision=revision+1 WHERE id=%s",
                (conversation_id,),
            )
            await conn.execute(
                "UPDATE support_app.escalations SET status='cancelled' WHERE conversation_id=%s",
                (conversation_id,),
            )
            await insert_operation(
                conn, owner, key, "delete", conversation_id, digest, conversation_id
            )
