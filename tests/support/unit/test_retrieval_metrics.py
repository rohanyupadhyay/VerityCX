"""Check retrieval measurements against literal, deliberately incomplete gold labels."""

import pytest

from veritycx.knowledge.models import CatalogEntry, EvidenceSection
from veritycx.knowledge.scope import CategoryCoverage, SearchScope
from veritycx.service.retrieval_cases import EvidenceExpectation


def section(document: str, suffix: str = "0001") -> EvidenceSection:
    """Create an independent source identity for metric arithmetic examples."""
    return EvidenceSection(
        corpus_version="fixture",
        document_id=document,
        section_id=f"{document}:{suffix}",
        section_hash="a" * 64,
        title=document,
        content="Policy.",
    )


def test_document_metrics_deduplicate_sections_and_keep_partial_gold_unknown() -> None:
    """Reject section-count inflation and assumed irrelevance of unlabeled sources."""
    from veritycx.service.retrieval_metrics import assess_evidence

    observed = (section("a"), section("a", "0002"), section("x"))
    gold = EvidenceExpectation(required_documents=("a", "b"), allowed_documents=("a", "b"))
    result = assess_evidence(gold, observed)
    assert result.required_document_recall == 0.5
    assert result.required_document_rr == 1
    assert result.allowed_document_precision == 0.5
    assert result.allowed_document_coverage == 0.5
    assert result.contract_passed is False
    unknown = assess_evidence(EvidenceExpectation(required_documents=("a",)), observed)
    assert unknown.allowed_document_precision is None
    assert unknown.allowed_document_coverage is None
    assert unknown.contract_passed is True


def test_empty_retrieval_does_not_invent_perfect_precision() -> None:
    """An empty answer has zero known-required recall and undefined precision/rank."""
    from veritycx.service.retrieval_metrics import assess_evidence

    result = assess_evidence(
        EvidenceExpectation(required_documents=("a",), allowed_documents=("a",)), ()
    )
    assert result.required_document_recall == 0
    assert result.required_document_rr == 0
    assert result.allowed_document_precision is None
    assert result.allowed_document_coverage == 0
    assert result.contract_passed is False


def test_unlabeled_cases_cannot_be_scored_as_passing_safety_checks() -> None:
    """Retrieving a policy for an unsupported attribute is not automatically wrong."""
    from veritycx.service.retrieval_metrics import assess_evidence

    for observed in ((), (section("a"),)):
        result = assess_evidence(EvidenceExpectation(), observed)
        assert result.contract_passed is None
        assert result.required_document_recall is None
        assert result.required_document_rr is None
    assert assess_evidence(EvidenceExpectation(), (), expected_empty=True).contract_passed is True
    wrong = assess_evidence(EvidenceExpectation(), (section("a"),), expected_empty=True)
    assert wrong.contract_passed is False and "empty_mismatch" in wrong.reasons


def test_reciprocal_rank_counts_distinct_documents() -> None:
    """Repeated irrelevant sections cannot push one known required document down twice."""
    from veritycx.service.retrieval_metrics import assess_evidence

    result = assess_evidence(
        EvidenceExpectation(required_documents=("a",)),
        (section("x"), section("x", "0002"), section("a")),
    )
    assert result.required_document_rr == 0.5


@pytest.mark.parametrize("fault", ["count", "balance", "forbidden", "section"])
def test_membership_alone_cannot_hide_other_authored_constraints(fault: str) -> None:
    """Wrong overview counts, balance, forbidden sources or absent sections fail the contract."""
    from veritycx.service.retrieval_metrics import assess_evidence

    gold = EvidenceExpectation(
        allowed_documents=("a", "b"),
        forbidden_documents=("b",) if fault == "forbidden" else (),
        required_sections=("a:0002",) if fault == "section" else (),
    )
    coverage = (
        CategoryCoverage(
            eligible_document_count=3, represented_document_count=3, coverage_truncated=False
        )
        if fault == "count"
        else None
    )
    result = assess_evidence(
        gold,
        (section("a"), section("b")),
        scope=SearchScope(scope="category_overview", categories=("cards",)),
        catalog_index=tuple(
            CatalogEntry(document_id=d, title=d, category="cards") for d in ("a", "b", "c")
        ),
        expected_coverage=coverage,
        minimum_category_documents={"accounts": 1} if fault == "balance" else None,
    )
    assert result.contract_passed is False
