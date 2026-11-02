"""Prove independent regression judgments reject corrupted pipeline observations."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import build_manifest, load_sections
from veritycx.knowledge.models import CatalogEntry
from veritycx.knowledge.scope import CategoryCoverage, SearchContext, SearchScope
from veritycx.persistence.rewrites import RewriteRow
from veritycx.policy.outputs import validate_result
from veritycx.providers.protocol import ContextMessage, ProviderRequest
from veritycx.providers.rewrite import RewriteRequest

if TYPE_CHECKING:
    from veritycx.service.retrieval_cases import RegressionTurn
    from veritycx.service.retrieval_checks import ObservedTurn


def overview() -> tuple[RegressionTurn, ObservedTurn, tuple[CatalogEntry, ...]]:
    """Build real publication data from three literal expected source identities."""
    from veritycx.service.retrieval_cases import load_cases, load_replays
    from veritycx.service.retrieval_checks import ObservedTurn

    cases = load_cases()
    turn = next(c for c in cases.scenarios if c.id == "broad-cards-original").turns[0]
    root, _, pin = source_mode("synthetic", validation=True)
    manifest = build_manifest(root, "synthetic", pin)
    assert manifest.catalog_index is not None
    replay = load_replays(cases, manifest)[("broad-cards-original", "t1")]
    evidence = tuple(
        s
        for s in load_sections(root, manifest)
        if s.document_id in {"policy-03", "policy-08", "policy-16"}
    )
    scope = SearchScope(scope="category_overview", categories=("cards",))
    coverage = CategoryCoverage(
        eligible_document_count=3, represented_document_count=3, coverage_truncated=False
    )
    request = ProviderRequest(
        question=turn.question,
        correlation_id="fixture",
        evidence=evidence,
        rewritten_query=turn.question,
        search_context=SearchContext(search_scope=scope, coverage=coverage),
        remaining_seconds=60.0,
    )
    row = RewriteRow(
        turn_id=uuid4(),
        request_digest="a" * 64,
        model="scripted-rewrite-v1",
        prompt_version=2,
        status="succeeded",
        result_json=replay.rewrite.model_dump_json(),
        failure_category=None,
        input_tokens=None,
        output_tokens=None,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        selected_source_ids=[s.section_id for s in evidence],
        retrieval_mode="category",
        expanded_term_count=0,
        search_scope="category_overview",
        category_keys=["cards"],
        eligible_document_count=3,
        represented_document_count=3,
        coverage_truncated=False,
    )
    assert replay.answer is not None
    observed = ObservedTurn(
        case_id="broad-cards-original",
        turn_id="t1",
        result=validate_result(request, replay.answer),
        rewrite=replay.rewrite,
        rewrite_requests=(
            RewriteRequest(
                question=turn.question,
                correlation_id="fixture",
                corpus_version=manifest.corpus_version,
                remaining_seconds=10.0,
            ),
        ),
        answer_requests=(request,),
        answer_results=(replay.answer,),
        rewrite_row=row,
        selected_sections=evidence,
        answer_attempts=1,
    )
    return turn, observed, manifest.catalog_index


def test_valid_observation_passes_all_four_boundaries() -> None:
    """The detector accepts a fully supported, cited and correctly scoped overview."""
    from veritycx.service.retrieval_checks import judge_turn

    turn, observed, catalog = overview()
    verdict = judge_turn(turn, observed, expected_history=(), catalog_index=catalog)
    assert verdict.passed
    assert all(
        getattr(verdict, key).status == "pass"
        for key in ("rewrite", "retrieval", "publication", "execution")
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing", "missing_evidence"),
        ("citation", "citation_mismatch"),
        ("scope", "scope_mismatch"),
        ("coverage", "coverage_mismatch"),
        ("question", "original_question_changed"),
        ("history", "history_mismatch"),
        ("kind", "disposition_mismatch"),
        ("note", "scope_note_missing"),
        ("budget", "budget_exceeded"),
        ("error", "execution_error"),
    ],
)
def test_detector_rejects_realistic_pipeline_corruption(change: str, reason: str) -> None:
    """A scripted answer cannot conceal wrong evidence, lost context or publication errors."""
    from veritycx.service.retrieval_checks import judge_turn

    turn, observed, catalog = overview()
    assert (
        observed.result is not None
        and observed.rewrite_row is not None
        and observed.rewrite is not None
    )
    published, rewrite, journal = observed.result, observed.rewrite, observed.rewrite_row
    history: tuple[ContextMessage, ...] = ()
    if change == "missing":
        observed = replace(observed, selected_sections=observed.selected_sections[:-1])
    elif change == "citation":
        observed = replace(
            observed,
            result=published.model_copy(update={"citations": published.citations[:-1]}),
        )
    elif change == "scope":
        observed = replace(
            observed,
            rewrite=rewrite.model_copy(
                update={
                    "result": rewrite.result.model_copy(
                        update={"scope": "focused", "categories": ()}
                    )
                }
            ),
        )
    elif change == "coverage":
        observed = replace(
            observed,
            rewrite_row=journal.model_copy(
                update={"represented_document_count": 2, "coverage_truncated": True}
            ),
        )
    elif change == "question":
        observed = replace(
            observed,
            rewrite_requests=(
                observed.rewrite_requests[0].model_copy(update={"question": "Different question"}),
            ),
        )
    elif change == "history":
        history = (ContextMessage(role="user", text="Prior Cedar question"),)
    elif change == "kind":
        observed = replace(observed, result=published.model_copy(update={"kind": "abstain"}))
    elif change == "note":
        observed = replace(
            observed, result=published.model_copy(update={"text": "Documented cards."})
        )
    elif change == "budget":
        observed = replace(observed, answer_attempts=3)
    else:
        observed = replace(observed, execution_error="PRIVATE_ERROR_CANARY")
    verdict = judge_turn(turn, observed, expected_history=history, catalog_index=catalog)
    assert not verdict.passed
    assert reason in [
        r
        for key in ("rewrite", "retrieval", "publication", "execution")
        for r in getattr(verdict, key).reasons
    ]


def test_failed_turn_cannot_disappear_from_run_success() -> None:
    """A single failed scenario or a completely unexecuted run is never green."""
    from veritycx.service.retrieval_checks import RegressionRun, ScenarioResult, judge_turn

    turn, observed, catalog = overview()
    bad = replace(observed, execution_error="timeout")
    verdict = judge_turn(turn, bad, expected_history=(), catalog_index=catalog)
    assert not RegressionRun(
        mode="offline",
        metadata={},
        scenarios=(ScenarioResult(case_id="bad", turns=((bad, verdict),)),),
    ).passed
    assert not RegressionRun(mode="offline", metadata={}, scenarios=()).passed


def test_explicit_forbidden_and_allowed_sets_are_enforced() -> None:
    """Existing evidence is still invalid when the gold contract excludes its product."""
    from veritycx.service.retrieval_cases import EvidenceExpectation
    from veritycx.service.retrieval_checks import check_evidence

    _, observed, _ = overview()
    assert check_evidence(
        EvidenceExpectation(forbidden_documents=("policy-16",)), observed.selected_sections
    ) == ("forbidden_evidence",)
    assert check_evidence(
        EvidenceExpectation(allowed_documents=("policy-03", "policy-08")),
        observed.selected_sections,
    ) == ("outside_allowed_evidence",)


RAW_CASES = [
    c["id"]
    for c in json.loads(
        (Path(__file__).parents[1] / "fixtures/retrieval-regressions.json").read_text()
    )["scenarios"]
    if c["turns"][0]["probe"] is not None
]


@pytest.mark.parametrize("case_id", RAW_CASES)
def test_raw_wording_retrieves_hand_authored_support(case_id: str) -> None:
    """Real NLP and retrieval must preserve expected support for linguistic variants."""
    from veritycx.knowledge.category_retrieval import select_scoped_evidence
    from veritycx.orchestration.rag import deterministic_rag
    from veritycx.service.retrieval_cases import load_cases
    from veritycx.service.retrieval_checks import check_evidence

    turn = next(c for c in load_cases().scenarios if c.id == case_id).turns[0]
    assert turn.probe is not None
    root, _, pin = source_mode("synthetic", validation=True)
    manifest = build_manifest(root, "synthetic", pin)
    assert manifest.catalog_index is not None
    rag = deterministic_rag()
    result = select_scoped_evidence(
        turn.question,
        turn.question,
        load_sections(root, manifest),
        search_scope=turn.probe.scope,
        catalog_index=manifest.catalog_index,
        normalizer=rag.normalizer,
        expander=rag.expander,
    )
    assert check_evidence(turn.probe.expected, result.sections) == ()
    if turn.probe.empty is not None:
        assert bool(result.sections) is not turn.probe.empty
    if turn.probe.scope.scope == "category_overview":
        assert result.expanded_term_count == 0


def test_auxiliary_word_alone_is_not_evidence() -> None:
    """The original does-match bug must not return arbitrary documents."""
    from veritycx.knowledge.retrieval import select_evidence
    from veritycx.orchestration.rag import deterministic_rag

    root, _, pin = source_mode("synthetic", validation=True)
    manifest = build_manifest(root, "synthetic", pin)
    rag = deterministic_rag()
    assert (
        select_evidence(
            "does",
            "does",
            load_sections(root, manifest),
            normalizer=rag.normalizer,
            expander=rag.expander,
        ).sections
        == ()
    )
