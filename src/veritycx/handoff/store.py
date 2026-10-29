"""Persist normalized intake, stable thread identity and irreversible publication claims."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from veritycx.handoff.configuration import ChatwootConfiguration
from veritycx.handoff.events import ChatwootEvent
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.models import ConversationRow, TurnRow
from veritycx.persistence.repository import Repository, RepositoryError, live_parent

NAMESPACE = UUID("510a34eb-5f09-4e38-8eb4-0b584ced5cff")


class Thread(BaseModel):
    """Represent a server-owned external mapping with durable handoff evidence."""

    model_config = ConfigDict(extra="ignore", strict=True)
    conversation_id: UUID
    owner_id: UUID
    external_id: int
    human_seen: bool
    observed_pause_id: UUID | None = None


class EventRow(BaseModel):
    """Read the bounded durable event fields consumed by the bridge."""

    model_config = ConfigDict(extra="ignore", strict=True)
    event_key: str
    message_id: int | None
    content: str | None


class Outbound(BaseModel):
    """Read one durable publication intent before any message POST."""

    model_config = ConfigDict(extra="ignore", strict=True)
    id: UUID
    turn_id: UUID
    kind: str
    content: str
    status: str


class ChatwootStore:
    """Keep each SQL transaction short; remote requests never hold application row locks."""

    def __init__(self, pool: DatabasePool, configuration: ChatwootConfiguration) -> None:
        """Bind a shared verified pool and the configured external account/inbox."""
        self.pool = pool
        self.config = configuration
        self.repository = Repository(pool)

    async def created_parent(self, owner: UUID, key: UUID) -> ConversationRow | None:
        """Recover the original corpus binding even before a thread mapping has committed."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT conversation_id FROM support_app.operations "
                "WHERE owner_id=%s AND request_key=%s AND kind='create'",
                (owner, key),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            conversation_id = row.get("conversation_id")
            if not isinstance(conversation_id, UUID):
                raise RepositoryError("incompatible_state")
            return await live_parent(conn, conversation_id, owner)

    async def persist(self, event: ChatwootEvent, corpus: str) -> None:
        """Persist the accepted projection before webhook acknowledgement with stable identity."""
        scope = (
            f"{self.config.base_url}:{self.config.account_id}:"
            f"{self.config.inbox_id}:{event.conversation_id}"
        )
        owner = uuid5(NAMESPACE, "owner:" + scope)
        key = uuid5(owner, "create")
        parent = await self.created_parent(owner, key)
        if parent is None:
            try:
                parent = await self.repository.create(owner, key, corpus)
            except RepositoryError as error:
                if str(error) != "idempotency_conflict":
                    raise
                # Another first webhook may have created the parent after our lookup,
                # using a corpus approved by a different service process.
                parent = await self.created_parent(owner, key)
                if parent is None:
                    raise
        async with transaction(self.pool) as conn:
            await live_parent(conn, parent.id, owner)
            await conn.execute(
                "INSERT INTO support_chatwoot.threads "
                "(conversation_id,account_id,inbox_id,external_id,owner_id,base_url) VALUES "
                "(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (conversation_id) DO UPDATE SET base_url=EXCLUDED.base_url "
                "WHERE support_chatwoot.threads.base_url IS NULL",
                (
                    parent.id,
                    self.config.account_id,
                    self.config.inbox_id,
                    event.conversation_id,
                    owner,
                    self.config.base_url,
                ),
            )
            await conn.execute(
                "INSERT INTO support_chatwoot.events "
                "(conversation_id,event_key,message_id,content) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (conversation_id,event_key) DO NOTHING",
                (parent.id, event.key, event.message_id, event.content),
            )
            await conn.execute(
                "UPDATE support_chatwoot.threads SET next_scan_at=clock_timestamp() "
                "WHERE conversation_id=%s",
                (parent.id,),
            )

    async def candidates(self) -> list[Thread]:
        """Scan a bounded fair batch of live mapped threads for events and completed answers."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT t.* FROM support_chatwoot.threads t "
                "JOIN support_app.conversations c ON c.id=t.conversation_id "
                "WHERE t.account_id=%s AND t.inbox_id=%s AND t.base_url=%s AND c.status<>'deleted' "
                "AND c.expires_at>clock_timestamp() AND t.next_scan_at<=clock_timestamp() "
                "ORDER BY t.next_scan_at LIMIT 50",
                (self.config.account_id, self.config.inbox_id, self.config.base_url),
            )
            return [Thread.model_validate(row) for row in await cursor.fetchall()]

    @asynccontextmanager
    async def locked(self, thread: Thread) -> AsyncIterator[bool]:
        """Serialize bridge instances by external thread using a bounded dedicated session lock."""
        lock = int.from_bytes(sha256(thread.conversation_id.bytes).digest()[:8], signed=True)
        async with self.pool.connection() as conn:
            cursor = await conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock,))
            row = await cursor.fetchone()
            held = row is not None and row["locked"] is True
            try:
                yield held
            finally:
                if held:
                    await conn.execute("SELECT pg_advisory_unlock(%s)", (lock,))

    async def defer(self, thread: Thread) -> None:
        """Throttle failed and idle remote scans while preserving fair progress."""
        async with transaction(self.pool) as conn:
            await conn.execute(
                "UPDATE support_chatwoot.threads SET "
                "next_scan_at=clock_timestamp()+interval '5 seconds' WHERE conversation_id=%s",
                (thread.conversation_id,),
            )

    async def events(self, thread: Thread) -> list[EventRow]:
        """Read only a bounded ordered batch, leaving busy acceptance durable for the next scan."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT * FROM support_chatwoot.events WHERE conversation_id=%s AND "
                "status='pending' ORDER BY message_id NULLS FIRST,created_at LIMIT 100",
                (thread.conversation_id,),
            )
            return [EventRow.model_validate(row) for row in await cursor.fetchall()]

    async def finish_event(self, thread: Thread, event: EventRow, turn_id: UUID | None) -> None:
        """Complete intake after core acceptance or explicit ownership suppression."""
        async with transaction(self.pool) as conn:
            await conn.execute(
                "UPDATE support_chatwoot.events SET status=%s,turn_id=%s WHERE "
                "conversation_id=%s AND event_key=%s",
                (
                    "accepted" if turn_id else "ignored",
                    turn_id,
                    thread.conversation_id,
                    event.event_key,
                ),
            )

    async def human_seen(self, thread: Thread) -> None:
        """Persist authoritative human ownership before considering future pause resumption."""
        async with transaction(self.pool) as conn:
            await live_parent(conn, thread.conversation_id, thread.owner_id)
            await conn.execute(
                "UPDATE support_chatwoot.threads SET human_seen=true,"
                "observed_pause_id=(SELECT pause_id "
                "FROM support_app.escalations WHERE conversation_id=%s AND status='pending') "
                "WHERE conversation_id=%s",
                (thread.conversation_id, thread.conversation_id),
            )
            # Persist a fence even for in-flight computation. Returning to pending must not
            # revive pre-takeover answers after a slow provider finishes.
            await conn.execute(
                "INSERT INTO support_chatwoot.outbound "
                "(id,conversation_id,turn_id,kind,content,status) "
                "SELECT id,conversation_id,id,'answer','Suppressed during human ownership.',"
                "'suppressed' FROM support_app.turns WHERE conversation_id=%s "
                "AND result->>'kind' IS DISTINCT FROM 'escalation' "
                "ON CONFLICT (turn_id,kind) DO UPDATE SET status='suppressed' "
                "WHERE support_chatwoot.outbound.status='ready'",
                (thread.conversation_id,),
            )

    async def completed(self, thread: Thread) -> list[TurnRow]:
        """Find unprojected terminal turns while excluding jobs still committing graph state."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT t.* FROM support_app.turns t "
                "JOIN support_app.conversations c ON c.id=t.conversation_id "
                "WHERE t.conversation_id=%s AND t.status IN ('completed','failed') "
                "AND c.active_job_id IS NULL AND t.result IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM support_chatwoot.outbound o WHERE o.turn_id=t.id "
                "AND o.kind=CASE WHEN t.result->>'kind'='escalation' THEN 'handoff' "
                "ELSE 'answer' END) "
                "ORDER BY t.sequence LIMIT 100",
                (thread.conversation_id,),
            )
            return [TurnRow.model_validate(row) for row in await cursor.fetchall()]

    async def intent(self, thread: Thread, turn: TurnRow, content: str, *, handoff: bool) -> None:
        """Record outgoing content and marker before any remote side effect."""
        async with transaction(self.pool) as conn:
            await live_parent(conn, thread.conversation_id, thread.owner_id)
            await conn.execute(
                "INSERT INTO support_chatwoot.outbound "
                "(id,conversation_id,turn_id,kind,content) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (
                    uuid5(turn.id, "handoff") if handoff else turn.id,
                    thread.conversation_id,
                    turn.id,
                    "handoff" if handoff else "answer",
                    content,
                ),
            )

    async def outgoing(self, thread: Thread) -> list[Outbound]:
        """Reconcile sending/uncertain intents after restart before attempting new messages."""
        async with transaction(self.pool) as conn:
            cursor = await conn.execute(
                "SELECT * FROM support_chatwoot.outbound WHERE conversation_id=%s "
                "AND status IN ('ready','sending','uncertain') ORDER BY created_at LIMIT 100",
                (thread.conversation_id,),
            )
            return [Outbound.model_validate(row) for row in await cursor.fetchall()]

    async def claim_publication(self, thread: Thread, outbound: Outbound) -> bool:
        """Commit a one-way publication claim; losing workers cannot repeat a message POST."""
        async with transaction(self.pool) as conn:
            await live_parent(conn, thread.conversation_id, thread.owner_id)
            cursor = await conn.execute(
                "UPDATE support_chatwoot.outbound SET status='sending' WHERE id=%s "
                "AND status='ready' RETURNING id",
                (outbound.id,),
            )
            return await cursor.fetchone() is not None

    async def publication(
        self, outbound: Outbound, status: str, message_id: int | None = None
    ) -> None:
        """Record only bounded delivery state, never provider exceptions or response bodies."""
        async with transaction(self.pool) as conn:
            await conn.execute(
                "UPDATE support_chatwoot.outbound SET status=%s,remote_message_id=%s WHERE id=%s",
                (status, message_id, outbound.id),
            )
