"""Measure only explicitly labeled retrieval requirements, preserving unknowns."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field

from veritycx.conversations.models import ClosedModel
from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.models import CatalogEntry, EvidenceSection
from veritycx.knowledge.scope import CategoryCoverage, SearchScope
from veritycx.service.retrieval_cases import EvidenceExpectation
from veritycx.service.retrieval_checks import check_evidence

ComparisonReason = Literal[
    "missing_evidence",
    "forbidden_evidence",
    "outside_allowed_evidence",
    "empty_mismatch",
    "coverage_mismatch",
    "budget_exceeded",
]


class EvidenceMetrics(ClosedModel):
    """Null means no applicable label or undefined precision, never an assumed success."""

    contract_passed: bool | None
    required_document_recall: float | None = Field(ge=0, le=1)
    required_document_rr: float | None = Field(ge=0, le=1)
    allowed_document_precision: float | None = Field(ge=0, le=1)
    allowed_document_coverage: float | None = Field(ge=0, le=1)
    reasons: tuple[ComparisonReason, ...] = ()


def assess_evidence(
    expected: EvidenceExpectation,
    sections: Sequence[EvidenceSection],
    *,
    scope: SearchScope | None = None,
    catalog_index: Sequence[CatalogEntry] = (),
    expected_empty: bool | None = None,
    expected_coverage: CategoryCoverage | None = None,
    minimum_category_documents: Mapping[CategoryKey, int] | None = None,
) -> EvidenceMetrics:
    """Compare independent gold sets with unique returned documents and literal bounds."""
    ordered = tuple(dict.fromkeys(s.document_id for s in sections))
    documents = set(ordered)
    required = set(expected.required_documents)
    allowed = set(expected.allowed_documents) if expected.allowed_documents is not None else None
    # check_evidence returns a wider reason union; keep the three membership labels explicit.
    membership = check_evidence(expected, sections)
    reasons: list[ComparisonReason] = []
    for reason in ("missing_evidence", "forbidden_evidence", "outside_allowed_evidence"):
        if reason in membership:
            reasons.append(reason)
    if expected_empty is not None and (not sections) != expected_empty:
        reasons.append("empty_mismatch")
    if (
        len(sections) > 6
        or len({s.section_id for s in sections}) != len(sections)
        or sum(len(s.content) for s in sections) > 12000
    ):
        reasons.append("budget_exceeded")
    minimum = minimum_category_documents or {}
    if expected_coverage is not None or minimum:
        eligible = {
            e.document_id: e.category
            for e in catalog_index
            if scope and e.category in scope.categories
        }
        truth = (len(eligible), len(documents), len(documents) < len(eligible))
        if not documents <= set(eligible) or (
            expected_coverage is not None
            and truth
            != (
                expected_coverage.eligible_document_count,
                expected_coverage.represented_document_count,
                expected_coverage.coverage_truncated,
            )
        ):
            reasons.append("coverage_mismatch")
        counts = Counter(eligible.get(d) for d in documents)
        if any(counts[key] < count for key, count in minimum.items()):
            reasons.append("coverage_mismatch")
    assessed = bool(
        required
        or expected.required_sections
        or expected.forbidden_documents
        or allowed is not None
        or expected_empty is not None
        or expected_coverage is not None
        or minimum
    )
    rank = next((i + 1 for i, d in enumerate(ordered) if d in required), None)
    return EvidenceMetrics(
        contract_passed=(not reasons) if assessed or reasons else None,
        required_document_recall=len(required & documents) / len(required) if required else None,
        required_document_rr=(1 / rank if rank else 0) if required else None,
        allowed_document_precision=len(allowed & documents) / len(documents)
        if allowed is not None and documents
        else None,
        allowed_document_coverage=len(allowed & documents) / len(allowed) if allowed else None,
        reasons=tuple(dict.fromkeys(reasons)),
    )
