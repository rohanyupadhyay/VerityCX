"""Coordinate durable Chatwoot intake, authoritative ownership and cautious publication."""

import asyncio
from uuid import uuid5

import httpx
from psycopg import Error
from psycopg_pool import PoolTimeout

from veritycx.conversations.models import ResumeInput, TurnResult
from veritycx.handoff.client import ChatwootClient, ChatwootRemoteError
from veritycx.handoff.configuration import ChatwootConfiguration
from veritycx.handoff.migrate import verify_chatwoot_schema
from veritycx.handoff.store import ChatwootStore, EventRow, Outbound, Thread
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.escalations import resume
from veritycx.persistence.repository import RepositoryError, live_parent
from veritycx.service.configuration import Settings


def render_answer(result: TurnResult) -> str:
    """Append bounded approved citation titles and section IDs to the grounded answer."""
    sources = [
        f"[{index}] {citation.title} ({citation.section_id})"
        for index, citation in enumerate(result.citations[:12], 1)
    ]
    return (result.text + ("\n\nSources:\n" + "\n".join(sources) if sources else ""))[:10000]


class ChatwootBridge:
    """Process mapped threads with replay-safe core requests and one-way publication claims."""

    def __init__(self, store: ChatwootStore, client: ChatwootClient) -> None:
        """Compose a durable store and a bounded remote client for deterministic testing."""
        self.store = store
        self.client = client

    async def resume_if_authorized(self, thread: Thread) -> bool:
        """Consume only a server-read pause/revision after verified remote return to bot control."""
        parent = await self.store.repository.get(thread.owner_id, thread.conversation_id)
        if parent.status != "escalation_pending":
            return parent.active_job_id is None
        if not thread.human_seen or parent.active_job_id is not None:
            return False
        async with transaction(self.store.pool) as conn:
            await live_parent(conn, thread.conversation_id, thread.owner_id)
            cursor = await conn.execute(
                "SELECT pause_id FROM support_app.escalations WHERE "
                "conversation_id=%s AND status='pending'",
                (thread.conversation_id,),
            )
            row = await cursor.fetchone()
        if row is None or row["pause_id"] != thread.observed_pause_id:
            return False
        # Verify immediately before consuming the server-authorized pause. No customer field
        # can choose ownership, pause ID, revision or continue_automation.
        if not (await self.client.conversation(thread.external_id)).bot_owned:
            return False
        value = ResumeInput(
            pause_id=str(row["pause_id"]),
            expected_revision=parent.revision,
            continue_automation=True,
        )
        await resume(
            self.store.pool,
            thread.owner_id,
            thread.conversation_id,
            uuid5(thread.owner_id, "resume:" + value.pause_id),
            value,
        )
        return False

    async def project(self, thread: Thread) -> None:
        """Turn terminal results into durable answer or bounded private handoff intentions."""
        for turn in await self.store.completed(thread):
            result = turn.result
            if result is None:
                continue
            handoff = result.kind == "escalation"
            if handoff:
                async with transaction(self.store.pool) as conn:
                    cursor = await conn.execute(
                        "SELECT summary FROM support_app.escalations WHERE "
                        "conversation_id=%s ORDER BY created_at DESC LIMIT 1",
                        (thread.conversation_id,),
                    )
                    row = await cursor.fetchone()
                summary = (
                    str(row["summary"])[:4000] if row else "Customer requested human assistance."
                )
                content = "VerityCX human handoff requested. Customer context:\n" + summary
            else:
                content = render_answer(result)
            await self.store.intent(thread, turn, content, handoff=handoff)

    async def publish(self, thread: Thread, outbound: Outbound) -> None:
        """Reconcile interrupted POSTs; never authorize another POST from an absent marker."""
        remote = await self.client.conversation(thread.external_id)
        if outbound.status in ("sending", "uncertain"):
            found = await self.client.find_message(thread.external_id, outbound.id)
            await self.store.publication(outbound, "sent" if found else "uncertain", found)
            return
        parent = await self.store.repository.get(thread.owner_id, thread.conversation_id)
        if outbound.kind == "handoff":
            # A consumed historical escalation must never reopen a thread returned to a bot.
            if parent.status != "escalation_pending":
                await self.store.publication(outbound, "suppressed")
                return
            if remote.bot_owned:
                await self.client.open(thread.external_id)
                remote = await self.client.conversation(thread.external_id)
            if remote.status != "open":
                return
            await self.store.human_seen(thread)
            # A private summary is deliberately allowed in the human inbox. Public automated
            # answers are suppressed whenever a human owns the remote thread.
        elif not remote.bot_owned or parent.status != "active":
            if not remote.bot_owned:
                await self.store.human_seen(thread)
            await self.store.publication(outbound, "suppressed")
            return
        if not await self.store.claim_publication(thread, outbound):
            return
        try:
            message_id = await self.client.message(
                thread.external_id,
                outbound.id,
                outbound.content,
                private=outbound.kind == "handoff",
            )
        except ChatwootRemoteError:
            await self.store.publication(outbound, "uncertain")
            return
        await self.store.publication(outbound, "sent", message_id)

    async def handoff_rejected_intake(self, thread: Thread, event: EventRow) -> None:
        """Retain terminally refused intake until the remote human handoff is confirmed."""
        remote = await self.client.conversation(thread.external_id)
        if remote.bot_owned:
            try:
                await self.client.open(thread.external_id)
            except ChatwootRemoteError:
                # Setting a specific status is idempotent. A lost response is reconciled
                # by authoritative GET; it must not discard the durable customer event.
                pass
            remote = await self.client.conversation(thread.external_id)
        if remote.status == "open":
            await self.store.human_seen(thread)
            await self.store.finish_event(thread, event, None)

    async def process(self, thread: Thread) -> None:
        """Publish prior results before intake so a terminal refusal cannot starve delivery."""
        remote = await self.client.conversation(thread.external_id)
        if not remote.bot_owned:
            await self.store.human_seen(thread)
        ready = remote.bot_owned and await self.resume_if_authorized(thread)
        await self.project(thread)
        for outbound in await self.store.outgoing(thread):
            await self.publish(thread, outbound)
        for event in await self.store.events(thread):
            if event.content is None:
                await self.store.finish_event(thread, event, None)
                continue
            if not ready:
                if not remote.bot_owned:
                    # Native Chatwoot retains human-owned context. Customer-controlled
                    # pending-without-assignment cannot start work or authorize resumption.
                    await self.store.finish_event(thread, event, None)
                break
            if not (await self.client.conversation(thread.external_id)).bot_owned:
                await self.store.human_seen(thread)
                break
            try:
                turn = await self.store.repository.accept(
                    thread.owner_id,
                    thread.conversation_id,
                    uuid5(thread.owner_id, event.event_key),
                    event.content,
                )
            except RepositoryError as error:
                if str(error) != "busy":
                    # Limits and incompatible/idempotency state need human attention.
                    # Existing outbounds were already projected/published above.
                    await self.handoff_rejected_intake(thread, event)
                break
            await self.store.finish_event(thread, event, turn.id)

    async def tick(self) -> None:
        """Process a bounded fair batch and isolate expected safe remote/storage failures."""
        for thread in await self.store.candidates():
            async with self.store.locked(thread) as held:
                if not held:
                    continue
                try:
                    await self.process(thread)
                except (ChatwootRemoteError, RepositoryError):
                    # Evidence remains durable; diagnostics never contain exception text.
                    pass
                finally:
                    await self.store.defer(thread)


async def run_bridge(
    pool: DatabasePool, configuration: ChatwootConfiguration, settings: Settings
) -> None:
    """Run a cancellation-safe continuous bridge, sharing the application's verified pool."""
    async with pool.connection() as conn:
        await verify_chatwoot_schema(conn)
    async with httpx.AsyncClient(
        trust_env=False, timeout=10, follow_redirects=False, limits=httpx.Limits(max_connections=4)
    ) as http:
        bridge = ChatwootBridge(
            ChatwootStore(pool, configuration), ChatwootClient(configuration, http)
        )
        while True:
            try:
                await bridge.tick()
            except (Error, PoolTimeout):
                pass
            await asyncio.sleep(settings.work_scan_seconds)
