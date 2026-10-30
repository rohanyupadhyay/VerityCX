"""Verify the actual worker stages with explicit offline dependencies and native storage."""

from dataclasses import replace
from uuid import uuid4

import pytest

from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.rag import deterministic_rag
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.protocol import ProviderError, ProviderRequest, ProviderResult
from veritycx.providers.rewrite import (
    REWRITE_RETRY_TEXT,
    RewriteRequest,
    RewriteResult,
    SearchRewrite,
)
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


class RecordingAnswer:
    """Capture only synthetic provider requests."""

    def __init__(self) -> None:
        """Start an empty synthetic request inventory."""
        self.calls: list[ProviderRequest] = []

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Return an abstention to prove it does not trigger another search."""
        self.calls.append(request)
        return ProviderResult(disposition="abstain", text="Fixture abstention.", model="fixture")


class RecordingRewrite:
    """Return a configured fixture query or fail deterministically."""

    def __init__(self, *, fail: bool = False) -> None:
        """Select an explicit offline failure mode."""
        self.fail = fail
        self.calls: list[RewriteRequest] = []

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Record the original question and return a fixed standalone search."""
        self.calls.append(request)
        if self.fail:
            raise ProviderError("provider_unavailable")
        return RewriteResult(
            result=SearchRewrite(disposition="search", query="Cedar card replacement fee"),
            model="rewrite-fixture",
        )


@pytest.mark.parametrize("fail", [False, True])
def test_every_knowledge_turn_rewrites_and_failure_stops_answering(
    test_database_url: str, fail: bool
) -> None:
    """A real graph records both stages or publishes only the explicit retry outcome."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            turn = await repo.accept(owner, parent.id, uuid4(), "What cards does VerityCX offers?")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            answer, rewrite = RecordingAnswer(), RecordingRewrite(fail=fail)
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert len(rewrite.calls) == 1
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
                assert row is not None
                result = row["result"]
                assert isinstance(result, dict)
                journal = await (
                    await conn.execute(
                        "SELECT * FROM support_app.query_rewrites WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
                assert journal is not None
            if fail:
                assert result["text"] == REWRITE_RETRY_TEXT
                assert not answer.calls and journal["retrieval_mode"] is None
                assert result["failure_category"] == "rewrite_provider_unavailable"
            else:
                assert len(answer.calls) == 1
                assert answer.calls[0].question == "What cards does VerityCX offers?"
                assert answer.calls[0].rewritten_query == "Cedar card replacement fee"
                assert journal["retrieval_mode"] == "primary"
                assert journal["selected_source_ids"]
                assert result["kind"] == "abstain"

    run_async(exercise())


def test_followup_uses_completed_same_conversation_history(test_database_url: str) -> None:
    """The real graph resolves a subject from the preceding completed customer turn."""

    async def exercise() -> None:
        """Keep policy evidence separate from the earlier assistant's abstention text."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            answer = RecordingAnswer()
            for question in ("Tell me about the Cedar card.", "What is its replacement fee?"):
                await repo.accept(owner, parent.id, uuid4(), question)
                job = await repo.claim(uuid4(), conversation_id=parent.id)
                assert job is not None
                await process_job(pool, job, Settings(), answer, rag=deterministic_rag())
            assert len(answer.calls) == 2
            followup = answer.calls[-1]
            assert followup.question == "What is its replacement fee?"
            assert followup.rewritten_query == "What is the Cedar card replacement fee?"
            assert followup.context[0].text == "Tell me about the Cedar card."
            assert any(section.document_id == "policy-03" for section in followup.evidence)

    run_async(exercise())


def test_ambiguous_followup_stops_before_answer_provider(test_database_url: str) -> None:
    """A missing subject requests clarification without spending an answer attempt."""

    async def exercise() -> None:
        """Exercise the actual typed clarification result and journal."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            turn = await repo.accept(owner, parent.id, uuid4(), "What is its replacement fee?")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            answer = RecordingAnswer()
            await process_job(pool, job, Settings(), answer, rag=deterministic_rag())
            assert answer.calls == []
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
                assert row is not None and isinstance(row["result"], dict)
                assert row["result"]["kind"] == "clarify"
                count = await (
                    await conn.execute(
                        "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                        (turn.id,),
                    )
                ).fetchone()
                assert count is not None and count["count"] == 0

    run_async(exercise())


def test_nlp_does_not_block_lease_renewal(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow synchronous selector leaves the event loop able to renew the real job."""
    import asyncio
    from threading import Event

    from veritycx.knowledge.retrieval import RetrievalSelection
    from veritycx.orchestration import graph

    started, released = Event(), Event()

    def slow_select(*args: object, **kwargs: object) -> RetrievalSelection:
        """Require a concurrent database renewal before returning."""
        started.set()
        assert released.wait(3), "event loop blocked by synchronous NLP"
        return RetrievalSelection((), "empty")

    monkeypatch.setattr(graph, "select_evidence", slow_select)

    async def exercise() -> None:
        """Run selection concurrently with a real fenced lease renewal."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            await repo.accept(owner, parent.id, uuid4(), "What cards are offered?")
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None

            async def release_after_renew() -> None:
                """Prove database progress occurs while NLP is still waiting."""
                while not started.is_set():
                    await asyncio.sleep(0.01)
                await repo.renew(job)
                released.set()

            await asyncio.wait_for(
                asyncio.gather(
                    process_job(pool, job, Settings(), RecordingAnswer(), rag=deterministic_rag()),
                    release_after_renew(),
                ),
                timeout=8,
            )

    run_async(exercise())
