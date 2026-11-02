"""Exercise actual fenced category retrieval with explicitly offline providers."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from veritycx.conversations.models import TurnResult
from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.configuration import active_corpus
from veritycx.knowledge.manifest import build_manifest, load_sections
from veritycx.knowledge.models import CorpusManifest
from veritycx.knowledge.scope import OVERVIEW_SCOPE_NOTE, category_hints
from veritycx.orchestration.rag import deterministic_rag
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import DatabasePool, database_pool
from veritycx.persistence.models import TurnRow, WorkJob
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.persistence.rewrites import RewriteLedger
from veritycx.providers.protocol import Claim, ProviderRequest, ProviderResult
from veritycx.providers.rewrite import RewriteRequest, RewriteResult, SearchRewrite
from veritycx.providers.rewrite_execution import invoke_rewriter
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


class RecordingRewriter:
    """Return explicit scope while recording the original bounded request."""

    def __init__(self, *, overview: bool = True) -> None:
        """Choose one authored scope rather than contacting a model."""
        self.calls: list[RewriteRequest] = []
        self.overview = overview
        self.categories: tuple[CategoryKey, ...] = ("cards",)

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Keep the original question intact so graph behavior is independently visible."""
        self.calls.append(request)
        return RewriteResult(
            result=SearchRewrite(
                disposition="search",
                query=request.question,
                scope="category_overview" if self.overview else "focused",
                categories=self.categories if self.overview else (),
            ),
            model="rewrite-fixture",
        )


class RecordingAnswer:
    """Cite selected authored policy titles or deliberately abstain."""

    def __init__(self, *, abstain: bool = False) -> None:
        """Start with no requests and an explicit test disposition."""
        self.calls: list[ProviderRequest] = []
        self.abstain = abstain

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Return control-flow evidence, not a simulated semantic-quality claim."""
        self.calls.append(request)
        if self.abstain:
            return ProviderResult(
                disposition="abstain", text="Unsupported qualifier.", model="fixture"
            )
        unique = {section.document_id: section for section in request.evidence}
        return ProviderResult(
            disposition="answer",
            model="fixture",
            claims=tuple(
                Claim(text="Documented policy: " + item.title, evidence_ids=(item.section_id,))
                for item in unique.values()
            ),
        )


async def accepted_job(
    pool: DatabasePool,
    manifest: CorpusManifest,
    question: str,
) -> tuple[Repository, TurnRow, WorkJob]:
    """Create a fresh synthetic owner and claim only this test's conversation."""
    repo = Repository(pool)
    owner = uuid4()
    parent = await repo.create(owner, uuid4(), manifest.corpus_version)
    turn = await repo.accept(owner, parent.id, uuid4(), question)
    job = await repo.claim(uuid4(), conversation_id=parent.id)
    assert job is not None
    with pytest.raises(RepositoryError, match="not_found"):
        await repo.get(uuid4(), parent.id)
    return repo, turn, job


def test_category_overview_records_coverage_and_current_prompt(test_database_url: str) -> None:
    """The actual graph includes Pine, cites all three documents and uses one call per stage."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        rewrite, answer = RecordingRewriter(), RecordingAnswer()
        async with database_pool(test_database_url) as pool:
            _, turn, job = await accepted_job(pool, manifest, "What cards does VerityCX offers?")
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert len(rewrite.calls) == len(answer.calls) == 1
            expected = {"policy-03", "policy-08", "policy-16"}
            assert {item.document_id for item in answer.calls[0].evidence} == expected
            assert any(hint.key == "cards" for hint in rewrite.calls[0].available_categories)
            assert answer.calls[0].search_context is not None
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
                journal = await (
                    await conn.execute(
                        "SELECT * FROM support_app.query_rewrites WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
                audit = await (
                    await conn.execute(
                        "SELECT prompt_version FROM support_app.audit WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
                attempts = await (
                    await conn.execute(
                        "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                        (turn.id,),
                    )
                ).fetchone()
            assert row is not None and journal is not None and audit is not None
            published = TurnResult.model_validate_json(json.dumps(row["result"]))
            assert published.text.endswith(OVERVIEW_SCOPE_NOTE)
            assert {item.document_id for item in published.citations} == expected
            assert journal["prompt_version"] == 2 and journal["retrieval_mode"] == "category"
            assert journal["search_scope"] == "category_overview"
            assert journal["category_keys"] == ["cards"]
            assert journal["eligible_document_count"] == journal["represented_document_count"] == 3
            assert journal["coverage_truncated"] is False and audit["prompt_version"] == 3
            assert attempts is not None and attempts["count"] == 1
            changes: list[dict[str, object]] = [
                {"category_keys": []},
                {"category_keys": ["unknown"]},
                {"search_scope": None},
                {"represented_document_count": 4},
                {"represented_document_count": 2},
                {"category_keys": ["cards"] * 7},
            ]
            for change in changes:
                async with pool.connection() as conn:
                    with pytest.raises(psycopg.errors.CheckViolation):
                        async with conn.transaction():
                            for key, value in change.items():
                                # Keys are fixed authored fixture names, never external SQL input.
                                from psycopg import sql

                                await conn.execute(
                                    sql.SQL(
                                        "UPDATE support_app.query_rewrites SET {}=%s "
                                        "WHERE turn_id=%s"
                                    ).format(sql.Identifier(key)),
                                    (Jsonb(value) if key == "category_keys" else value, turn.id),
                                )

    run_async(exercise())


@pytest.mark.parametrize(
    "question",
    [
        "Which cards are eligible for businesses?",
        "What is the fee for a Martian asteroid vault?",
    ],
)
def test_classifier_scope_does_not_erase_unsupported_qualifiers(
    test_database_url: str, question: str
) -> None:
    """A wrong overview classification cannot replace the answer provider's original question."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        rewrite, answer = RecordingRewriter(), RecordingAnswer(abstain=True)
        async with database_pool(test_database_url) as pool:
            _, turn, job = await accepted_job(pool, manifest, question)
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert len(answer.calls) == len(rewrite.calls) == 1
            assert answer.calls[0].question == question
            assert answer.calls[0].rewritten_query == question
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
            assert row is not None
            published = TurnResult.model_validate_json(json.dumps(row["result"]))
            assert published.kind == "abstain"
            assert OVERVIEW_SCOPE_NOTE not in published.text

    run_async(exercise())


@pytest.mark.parametrize("oversized", [False, True])
def test_empty_or_uncitable_category_never_spends_answer_attempt(
    test_database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, oversized: bool
) -> None:
    """Empty categories abstain; a group larger than the budget requests narrower scope."""
    from veritycx.orchestration import graph

    for number in range(7 if oversized else 1):
        (tmp_path / f"{number}.json").write_text(
            json.dumps(
                {
                    "id": str(number),
                    "title": "Card policy versions" if oversized else "Savings",
                    "content": "An authored fixture policy.",
                }
            )
        )
    manifest = build_manifest(tmp_path, "synthetic", "fixture")
    corpus = load_sections(tmp_path, manifest)
    monkeypatch.setattr(graph, "active_corpus", lambda mode: (manifest, corpus))

    async def exercise() -> None:
        rewrite, answer = RecordingRewriter(), RecordingAnswer()
        async with database_pool(test_database_url) as pool:
            _, turn, job = await accepted_job(pool, manifest, "What card options are documented?")
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert len(rewrite.calls) == 1 and not answer.calls
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
                diagnostics = await (
                    await conn.execute(
                        "SELECT search_scope,eligible_document_count,coverage_truncated "
                        "FROM support_app.query_rewrites WHERE turn_id=%s",
                        (turn.id,),
                    )
                ).fetchone()
                attempts = await (
                    await conn.execute(
                        "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                        (turn.id,),
                    )
                ).fetchone()
            assert row is not None and diagnostics is not None
            published = TurnResult.model_validate_json(json.dumps(row["result"]))
            assert published.kind == ("clarify" if oversized else "abstain")
            assert diagnostics["search_scope"] == "category_overview"
            assert diagnostics["eligible_document_count"] == (7 if oversized else 0)
            assert diagnostics["coverage_truncated"] == oversized
            assert attempts is not None and attempts["count"] == 0

    run_async(exercise())


def test_successful_overview_rewrite_reuses_ledger_and_rejects_changed_hints(
    test_database_url: str,
) -> None:
    """A restart between durable rewrite success and selection cannot issue another rewrite."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        assert manifest.catalog_index is not None
        rewrite, answer = RecordingRewriter(), RecordingAnswer()
        async with database_pool(test_database_url) as pool:
            _, turn, job = await accepted_job(pool, manifest, "What cards are documented?")
            async with pool.connection() as conn:
                audit = await (
                    await conn.execute(
                        "SELECT correlation_id FROM support_app.audit WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
            assert audit is not None
            request = RewriteRequest(
                question=turn.text,
                correlation_id=str(audit["correlation_id"]),
                corpus_version=manifest.corpus_version,
                remaining_seconds=60.0,
                available_categories=category_hints(manifest.catalog_index),
            )
            await invoke_rewriter(
                rewrite, RewriteLedger(pool), job, request, Settings().effective_rewrite_model
            )
            with pytest.raises(RepositoryError, match="incompatible_state"):
                await invoke_rewriter(
                    rewrite,
                    RewriteLedger(pool),
                    job,
                    request.model_copy(update={"available_categories": ()}),
                    Settings().effective_rewrite_model,
                )
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert len(rewrite.calls) == len(answer.calls) == 1

    run_async(exercise())


def test_legacy_conversation_mismatch_stops_before_rewrite(test_database_url: str) -> None:
    """A v2 conversation cannot silently gain category behavior or a new paid attempt."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        rewrite, answer = RecordingRewriter(), RecordingAnswer()
        async with database_pool(test_database_url) as pool:
            _, turn, job = await accepted_job(
                pool, manifest.model_copy(update={"corpus_version": "legacy-v2"}), "What cards?"
            )
            await process_job(
                pool, job, Settings(), answer, rag=replace(deterministic_rag(), rewriter=rewrite)
            )
            assert not rewrite.calls and not answer.calls
            async with pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
            assert row is not None
            published = TurnResult.model_validate_json(json.dumps(row["result"]))
            assert published.failure_category == "corpus_changed"

    run_async(exercise())


def test_topic_change_uses_the_current_turn_scope(test_database_url: str) -> None:
    """A prior cards overview cannot bind the next explicit savings question."""

    async def exercise() -> None:
        manifest, _ = active_corpus("synthetic")
        rewrite, answer = RecordingRewriter(), RecordingAnswer()
        async with database_pool(test_database_url) as pool:
            repo, owner = Repository(pool), uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            cases: list[tuple[str, tuple[CategoryKey, ...]]] = [
                ("What cards are documented?", ("cards",)),
                ("What savings policies are documented?", ("savings",)),
            ]
            for question, categories in cases:
                rewrite.categories = categories
                await repo.accept(owner, parent.id, uuid4(), question)
                job = await repo.claim(uuid4(), conversation_id=parent.id)
                assert job is not None
                await process_job(
                    pool,
                    job,
                    Settings(),
                    answer,
                    rag=replace(deterministic_rag(), rewriter=rewrite),
                )
            assert len(rewrite.calls) == len(answer.calls) == 2
            assert rewrite.calls[1].context[0].text == "What cards are documented?"
            assert {item.document_id for item in answer.calls[1].evidence} == {
                "policy-01",
                "policy-06",
                "policy-17",
            }
            assert answer.calls[1].search_context is not None
            assert answer.calls[1].search_context.search_scope.categories == ("savings",)

    run_async(exercise())
