"""Exercise durable Chatwoot intake, restart recovery, handoff and retention in a test DB."""

import json
import os
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from psycopg import sql

from tests.support.harness import require_test_database
from tests.support.unit.test_chatwoot import environment
from veritycx.handoff.bridge import ChatwootBridge
from veritycx.handoff.client import ChatwootClient
from veritycx.handoff.configuration import ChatwootConfiguration, load_chatwoot_configuration
from veritycx.handoff.events import ChatwootEvent
from veritycx.handoff.migrate import migrate_chatwoot, verify_chatwoot_schema
from veritycx.handoff.store import ChatwootStore, Thread
from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import DatabasePool, database_pool, transaction
from veritycx.persistence.maintenance import purge_expired
from veritycx.persistence.repository import RepositoryError
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def configuration() -> ChatwootConfiguration:
    """Use a unique synthetic account per case so persisted tests never share mappings."""
    env = environment()
    env["VERITYCX_CHATWOOT_ACCOUNT_ID"] = str(uuid4().int % 1000000000 + 1)
    result = load_chatwoot_configuration(env)
    assert result is not None
    return result


async def prepare(
    pool: DatabasePool,
    config: ChatwootConfiguration,
    message: str = "What is the replacement card fee?",
) -> tuple[ChatwootStore, Thread]:
    """Persist one event twice and recover its single durable server-owned mapping."""
    admin = require_test_database(os.environ.get("VERITYCX_TEST_MIGRATION_DATABASE_URL", ""))
    await migrate_chatwoot(admin, "veritycx_support_test")
    store = ChatwootStore(pool, config)
    manifest, _ = active_corpus("synthetic")
    event = ChatwootEvent("message:9", 7, 9, message)
    await store.persist(event, manifest.corpus_version)
    await store.persist(event, manifest.corpus_version)
    threads = await store.candidates()
    assert len(threads) == 1
    return store, threads[0]


async def execute(pool: DatabasePool, store: ChatwootStore, thread: Thread) -> None:
    """Complete one actual core graph job through the existing deterministic worker."""
    job = await store.repository.claim(uuid4(), conversation_id=thread.conversation_id)
    assert job is not None
    await process_job(pool, job, Settings(), DeterministicProvider())


def test_chatwoot_migration_and_cascading_retention(test_database_url: str) -> None:
    """Repeat the independent migration and cascade integration rows with the core parent."""
    admin = require_test_database(os.environ.get("VERITYCX_TEST_MIGRATION_DATABASE_URL", ""))

    async def exercise() -> None:
        await migrate_chatwoot(admin, "veritycx_support_test")
        await migrate_chatwoot(admin, "veritycx_support_test")
        async with database_pool(test_database_url) as pool:
            async with pool.connection() as conn:
                await verify_chatwoot_schema(conn)
            store, thread = await prepare(pool, configuration())
            with pytest.raises(RepositoryError, match="not_found"):
                await store.repository.get(uuid4(), thread.conversation_id)
            assert len(await store.events(thread)) == 1
            await store.repository.delete(thread.owner_id, thread.conversation_id, uuid4())
            assert await purge_expired(pool, target=thread.conversation_id) == 1
            async with transaction(pool) as conn:
                for table in ("threads", "events", "outbound"):
                    cursor = await conn.execute(
                        sql.SQL("SELECT count(*) AS total FROM {} WHERE conversation_id=%s").format(
                            sql.Identifier("support_chatwoot", table)
                        ),
                        (thread.conversation_id,),
                    )
                    row = await cursor.fetchone()
                    assert row is not None and row["total"] == 0

    run_async(exercise())


@pytest.mark.parametrize("mapping_exists", [True, False])
def test_chatwoot_corpus_update_preserves_existing_thread(
    test_database_url: str, mapping_exists: bool
) -> None:
    """Accept replay and new messages without rebinding an existing chat to new documents."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config)
            original = await store.repository.get(thread.owner_id, thread.conversation_id)
            if not mapping_exists:
                # Model interruption after parent creation but before the mapping commits.
                async with transaction(pool) as conn:
                    await conn.execute(
                        "DELETE FROM support_chatwoot.threads WHERE conversation_id=%s",
                        (thread.conversation_id,),
                    )
            replacement = original.corpus_version + "-replacement"
            await store.persist(
                ChatwootEvent("message:9", 7, 9, "What is the replacement card fee?"),
                replacement,
            )
            await store.persist(
                ChatwootEvent("message:10", 7, 10, "What is the Birch checking monthly fee?"),
                replacement,
            )
            threads = await store.candidates()
            assert len(threads) == 1 and threads[0].conversation_id == thread.conversation_id
            parent = await store.repository.get(thread.owner_id, thread.conversation_id)
            assert parent.corpus_version == original.corpus_version
            assert len(await store.events(thread)) == 2

    run_async(exercise())


def test_chatwoot_restart_reconciles_uncertain_post(test_database_url: str) -> None:
    """Recover the remote marker after a successful POST whose response was lost."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config)
            posted: list[dict[str, object]] = []

            def remote(request: httpx.Request) -> httpx.Response:
                if request.method == "POST":
                    posted.append(json.loads(request.content))
                    raise httpx.ReadTimeout("synthetic lost response")
                if request.url.path.endswith("/messages"):
                    return httpx.Response(200, json={"payload": [dict(posted[0], id=22)]})
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": "pending",
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                await execute(pool, store, thread)
                await bridge.process(thread)
                assert len(posted) == 1
                pending = await store.outgoing(thread)
                assert len(pending) == 1 and pending[0].status == "uncertain"
                restarted = ChatwootBridge(
                    ChatwootStore(pool, config), ChatwootClient(config, http)
                )
                await restarted.process(thread)
                assert len(posted) == 1 and await store.outgoing(thread) == []
                async with transaction(pool) as conn:
                    cursor = await conn.execute(
                        "SELECT remote_message_id FROM support_chatwoot.outbound "
                        "WHERE conversation_id=%s",
                        (thread.conversation_id,),
                    )
                    row = await cursor.fetchone()
                    assert row is not None and row["remote_message_id"] == 22

    run_async(exercise())


def test_chatwoot_absent_marker_never_reposts(test_database_url: str) -> None:
    """An uncertain send with no visible remote marker remains an operator decision."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config)
            posts = 0

            def remote(request: httpx.Request) -> httpx.Response:
                nonlocal posts
                if request.method == "POST":
                    posts += 1
                    raise httpx.ReadTimeout("synthetic lost response")
                if request.url.path.endswith("/messages"):
                    return httpx.Response(200, json={"payload": []})
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": "pending",
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                await execute(pool, store, thread)
                await bridge.process(thread)
                await bridge.process(thread)
                assert posts == 1
                assert (await store.outgoing(thread))[0].status == "uncertain"

    run_async(exercise())


def test_chatwoot_handoff_and_authoritative_resume(test_database_url: str) -> None:
    """Open a real human handoff, send only a private summary and resume after remote pending."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config, "I want a human agent")
            status = "pending"
            assigned = True
            messages: list[dict[str, object]] = []

            def remote(request: httpx.Request) -> httpx.Response:
                nonlocal status, assigned
                if request.url.path.endswith("/toggle_status"):
                    status = str(json.loads(request.content)["status"])
                    assigned = False
                    return httpx.Response(200, json={"status": status})
                if request.method == "POST":
                    messages.append(json.loads(request.content))
                    return httpx.Response(200, json={"id": 31})
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": status,
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}}
                        if assigned
                        else {},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                await execute(pool, store, thread)
                await bridge.process(thread)
                assert status == "open" and len(messages) == 1
                assert messages[0]["private"] is True
                assert "nobody has been notified" not in str(messages[0]["content"])
                manifest, _ = active_corpus("synthetic")
                await store.persist(
                    ChatwootEvent("message:10", 7, 10, "continue automation"),
                    manifest.corpus_version,
                )
                refreshed = (await store.candidates())[0]
                await bridge.process(refreshed)
                assert (
                    await store.repository.claim(uuid4(), conversation_id=thread.conversation_id)
                    is None
                )
                assert (
                    await store.repository.get(thread.owner_id, thread.conversation_id)
                ).status == "escalation_pending"
                # A customer resolving and messaging can produce pending without assignment.
                # That transition is not staff consent to resume automation.
                status = "pending"
                await bridge.process(refreshed)
                assert (
                    await store.repository.get(thread.owner_id, thread.conversation_id)
                ).active_job_id is None
                assigned = True  # Only staff assigning an AgentBot establishes authority.
                await bridge.process(refreshed)
                await execute(pool, store, thread)
                assert (
                    await store.repository.get(thread.owner_id, thread.conversation_id)
                ).status == "active"
                assert len(messages) == 1

    run_async(exercise())


def test_chatwoot_previous_human_ownership_cannot_resume_new_pause(test_database_url: str) -> None:
    """A historical human takeover cannot satisfy authorization for a later pause."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config, "I want a human agent")
            # The prior takeover was observed while the core conversation was active.
            await store.human_seen(thread)
            refreshed = (await store.candidates())[0]

            def remote(request: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": "pending",
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(refreshed)
                await execute(pool, store, thread)
                assert await bridge.resume_if_authorized(refreshed) is False
                assert (
                    await store.repository.claim(uuid4(), conversation_id=thread.conversation_id)
                    is None
                )

    run_async(exercise())


def test_chatwoot_origin_change_cannot_reuse_mapping(test_database_url: str) -> None:
    """Identical account/inbox/thread IDs on different servers receive isolated internal owners."""

    async def exercise() -> None:
        first = configuration()
        second = replace(first, base_url="https://example.invalid")
        async with database_pool(test_database_url) as pool:
            old_store, old = await prepare(pool, first)
            new_store, new = await prepare(pool, second)
            assert old.conversation_id != new.conversation_id and old.owner_id != new.owner_id
            assert (await old_store.candidates())[0].conversation_id == old.conversation_id
            assert (await new_store.candidates())[0].conversation_id == new.conversation_id

    run_async(exercise())


def test_chatwoot_takeover_suppresses_inflight_answer_after_return(test_database_url: str) -> None:
    """Returning a thread to pending cannot revive an answer computed before observed takeover."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config)
            status = "pending"
            posts = 0

            def remote(request: httpx.Request) -> httpx.Response:
                nonlocal posts
                if request.method == "POST":
                    posts += 1
                    return httpx.Response(200, json={"id": 44})
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": status,
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                status = "open"
                await bridge.process(thread)
                status = "pending"
                await execute(pool, store, thread)
                await bridge.process(thread)
                assert posts == 0 and await store.outgoing(thread) == []

    run_async(exercise())


@pytest.mark.parametrize("failure", ["conversation_limit", "incompatible_state"])
def test_chatwoot_terminal_intake_preserves_answer_and_hands_off(
    test_database_url: str, failure: str
) -> None:
    """Publish the final answer before routing an unserviceable next customer message to staff."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config)
            if failure == "conversation_limit":
                # Seed the bounded boundary rather than executing 99 irrelevant provider jobs.
                async with transaction(pool) as conn:
                    await conn.execute(
                        "UPDATE support_app.conversations SET customer_count=99 WHERE id=%s",
                        (thread.conversation_id,),
                    )
            status = "pending"
            posted: list[dict[str, object]] = []
            opens = 0

            def remote(request: httpx.Request) -> httpx.Response:
                nonlocal status, opens
                if request.url.path.endswith("/toggle_status"):
                    opens += 1
                    status = str(json.loads(request.content)["status"])
                    return httpx.Response(200, json={"status": status})
                if request.method == "POST":
                    assert status == "pending"
                    posted.append(json.loads(request.content))
                    return httpx.Response(200, json={"id": 55})
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": status,
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                await execute(pool, store, thread)
                if failure == "incompatible_state":
                    async with transaction(pool) as conn:
                        await conn.execute(
                            "UPDATE support_app.jobs SET status='failed',"
                            "failure_code='incompatible_state' WHERE conversation_id=%s",
                            (thread.conversation_id,),
                        )
                manifest, _ = active_corpus("synthetic")
                await store.persist(
                    ChatwootEvent("message:10", 7, 10, "I want a human agent"),
                    manifest.corpus_version,
                )
                await bridge.process(thread)
                assert len(posted) == 1 and posted[0]["private"] is False
                assert status == "open" and opens == 1
                assert await store.events(thread) == []
                assert await store.outgoing(thread) == []
                await bridge.process(thread)
                assert len(posted) == 1 and opens == 1

    run_async(exercise())


def test_chatwoot_terminal_handoff_retains_event_until_open_confirmed(
    test_database_url: str,
) -> None:
    """Keep refused customer intake retryable when the status-set response is ambiguous."""

    async def exercise() -> None:
        config = configuration()
        async with database_pool(test_database_url) as pool:
            store, thread = await prepare(pool, config, "I want a human agent")
            async with transaction(pool) as conn:
                await conn.execute(
                    "UPDATE support_app.conversations SET customer_count=100 WHERE id=%s",
                    (thread.conversation_id,),
                )
            status = "pending"
            opens = 0

            def remote(request: httpx.Request) -> httpx.Response:
                nonlocal status, opens
                if request.url.path.endswith("/toggle_status"):
                    opens += 1
                    if opens > 1:
                        status = "open"
                    raise httpx.ReadTimeout("synthetic uncertain status update")
                assert request.method == "GET"
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": status,
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
                bridge = ChatwootBridge(store, ChatwootClient(config, http))
                await bridge.process(thread)
                assert status == "pending" and len(await store.events(thread)) == 1
                await bridge.process(thread)
                assert status == "open" and await store.events(thread) == []
                await bridge.process(thread)
                assert opens == 2

    run_async(exercise())
