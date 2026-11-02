"""Judge captured regression behavior without exposing expectations to providers."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from veritycx.conversations.models import ClosedModel, TurnResult
from veritycx.knowledge.models import CatalogEntry, EvidenceSection
from veritycx.knowledge.scope import OVERVIEW_SCOPE_NOTE
from veritycx.persistence.rewrites import RewriteRow
from veritycx.providers.protocol import ContextMessage, ProviderRequest, ProviderResult
from veritycx.providers.rewrite import RewriteRequest, RewriteResult, SearchRewrite
from veritycx.service.retrieval_cases import EvidenceExpectation, RegressionTurn

Reason = Literal[
    "missing_evidence",
    "forbidden_evidence",
    "outside_allowed_evidence",
    "citation_mismatch",
    "scope_mismatch",
    "coverage_mismatch",
    "original_question_changed",
    "history_mismatch",
    "disposition_mismatch",
    "scope_note_missing",
    "budget_exceeded",
    "execution_error",
    "rewrite_kind_mismatch",
    "journal_mismatch",
    "evidence_mismatch",
    "dependency_failed",
]


@dataclass
class CallRecorder:
    """Capture actual adapter inputs and outputs in invocation order."""

    rewrite_requests: list[RewriteRequest] = field(default_factory=list)
    rewrite_results: list[RewriteResult | None] = field(default_factory=list)
    answer_requests: list[ProviderRequest] = field(default_factory=list)
    answer_results: list[ProviderResult | None] = field(default_factory=list)


@dataclass(frozen=True)
class ObservedTurn:
    """Keep private observations distinct from public verdict metadata."""

    case_id: str
    turn_id: str
    result: TurnResult | None = None
    rewrite: RewriteResult | None = None
    rewrite_requests: tuple[RewriteRequest, ...] = ()
    answer_requests: tuple[ProviderRequest, ...] = ()
    answer_results: tuple[ProviderResult | None, ...] = ()
    rewrite_row: RewriteRow | None = None
    selected_sections: tuple[EvidenceSection, ...] = ()
    answer_attempts: int = 0
    elapsed_ms: int = 0
    execution_error: str | None = None


class BoundaryVerdict(ClosedModel):
    """Allow only finite, content-free reasons into public reports."""

    status: Literal["pass", "fail", "not_run"]
    reasons: tuple[Reason, ...] = ()


class TurnVerdict(ClosedModel):
    """Separate interpretation, evidence, publication and execution outcomes."""

    rewrite: BoundaryVerdict
    retrieval: BoundaryVerdict
    publication: BoundaryVerdict
    execution: BoundaryVerdict

    @property
    def passed(self) -> bool:
        """Unexecuted and failed turns cannot be reported as successful cases."""
        return self.execution.status == "pass" and all(
            item.status != "fail" for item in (self.rewrite, self.retrieval, self.publication)
        )


@dataclass(frozen=True)
class ScenarioResult:
    """Retain every attempted or dependent-unexecuted turn in a scenario."""

    case_id: str
    turns: tuple[tuple[ObservedTurn, TurnVerdict], ...]


@dataclass(frozen=True)
class RegressionRun:
    """Carry private review evidence and a conservative overall verdict."""

    mode: Literal["offline", "live"]
    metadata: dict[str, object]
    scenarios: tuple[ScenarioResult, ...]

    @property
    def passed(self) -> bool:
        """An empty run or one failed case is not success."""
        return bool(self.scenarios) and all(
            case.turns and all(verdict.passed for _, verdict in case.turns)
            for case in self.scenarios
        )


def _verdict(reasons: Sequence[Reason], *, ran: bool = True) -> BoundaryVerdict:
    """Deduplicate fixed labels while retaining their diagnostic order."""
    return BoundaryVerdict(
        status="fail" if reasons else ("pass" if ran else "not_run"),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def check_evidence(
    expected: EvidenceExpectation, sections: Sequence[EvidenceSection]
) -> tuple[Reason, ...]:
    """Compare actual support to literal gold sets, never to another selector call."""
    documents = {section.document_id for section in sections}
    identifiers = {section.section_id for section in sections}
    reasons: list[Reason] = []
    if (
        not set(expected.required_documents) <= documents
        or not set(expected.required_sections) <= identifiers
    ):
        reasons.append("missing_evidence")
    if set(expected.forbidden_documents) & documents:
        reasons.append("forbidden_evidence")
    if expected.allowed_documents is not None and not documents <= set(expected.allowed_documents):
        reasons.append("outside_allowed_evidence")
    return tuple(reasons)


def judge_turn(
    turn: RegressionTurn,
    observed: ObservedTurn,
    *,
    expected_history: tuple[ContextMessage, ...],
    catalog_index: Sequence[CatalogEntry],
) -> TurnVerdict:
    """Check a committed turn and captured requests independently of scripted responses."""
    rewrite_errors: list[Reason] = []
    evidence_errors: list[Reason] = []
    publication_errors: list[Reason] = []
    execution_errors: list[Reason] = []
    if observed.execution_error == "dependency_failed":
        return TurnVerdict(
            rewrite=_verdict((), ran=False),
            retrieval=_verdict((), ran=False),
            publication=_verdict((), ran=False),
            execution=_verdict(("dependency_failed",)),
        )
    if observed.execution_error or observed.result is None or observed.result.kind == "error":
        execution_errors.append("execution_error")
    if (
        len(observed.rewrite_requests) != 1
        or not 0 <= observed.answer_attempts <= 2
        or len(observed.answer_requests) != observed.answer_attempts
    ):
        execution_errors.append("budget_exceeded")
    if any(request.remaining_seconds > 10 for request in observed.rewrite_requests):
        execution_errors.append("budget_exceeded")
    requests: tuple[RewriteRequest | ProviderRequest, ...] = (
        *observed.rewrite_requests,
        *observed.answer_requests,
    )
    for request in requests:
        if request.question != turn.question:
            rewrite_errors.append("original_question_changed")
        if (
            request.context != expected_history
            or sum(len(item.text) for item in expected_history) > 16000
        ):
            rewrite_errors.append("history_mismatch")
    rewrite = observed.rewrite.result if observed.rewrite else None
    row = observed.rewrite_row
    if rewrite is None or rewrite.disposition not in turn.expected.rewrite_kinds:
        rewrite_errors.append("rewrite_kind_mismatch")
    if row is None or row.status != "succeeded" or row.prompt_version != 2:
        rewrite_errors.append("journal_mismatch")
    elif observed.rewrite is not None:
        try:
            if (
                row.result_json is None
                or RewriteResult.model_validate_json(row.result_json) != observed.rewrite
            ):
                rewrite_errors.append("journal_mismatch")
        except ValueError:
            rewrite_errors.append("journal_mismatch")
    if isinstance(rewrite, SearchRewrite):
        scope = rewrite.search_scope()
        if scope not in turn.expected.scopes:
            rewrite_errors.append("scope_mismatch")
        evidence_errors.extend(check_evidence(turn.expected.evidence, observed.selected_sections))
        ids = tuple(section.section_id for section in observed.selected_sections)
        if (
            len(ids) != len(set(ids))
            or len(ids) > 6
            or sum(len(s.content) for s in observed.selected_sections) > 12000
        ):
            execution_errors.append("budget_exceeded")
        if row is None or tuple(row.selected_source_ids) != ids:
            evidence_errors.append("journal_mismatch")
        if row is not None:
            if (
                row.search_scope != scope.scope
                or tuple(row.category_keys or ()) != scope.categories
            ):
                rewrite_errors.append("scope_mismatch")
            if scope.scope == "category_overview":
                eligible = {
                    entry.document_id: entry.category
                    for entry in catalog_index
                    if entry.category in scope.categories
                }
                represented = {s.document_id for s in observed.selected_sections}
                actual = (
                    row.eligible_document_count,
                    row.represented_document_count,
                    row.coverage_truncated,
                )
                truth = (len(eligible), len(represented), len(represented) < len(eligible))
                if actual != truth or not represented <= set(eligible):
                    evidence_errors.append("coverage_mismatch")
                if turn.expected.coverage is not None:
                    coverage = turn.expected.coverage
                    if actual != (
                        coverage.eligible_document_count,
                        coverage.represented_document_count,
                        coverage.coverage_truncated,
                    ):
                        evidence_errors.append("coverage_mismatch")
                counts = Counter(eligible.get(identifier) for identifier in represented)
                if any(
                    counts[category] < minimum
                    for category, minimum in turn.expected.minimum_category_documents.items()
                ):
                    evidence_errors.append("coverage_mismatch")
                if row.expanded_term_count or row.retrieval_mode != (
                    "category" if ids else "empty"
                ):
                    evidence_errors.append("scope_mismatch")
            elif any(
                value is not None
                for value in (
                    row.eligible_document_count,
                    row.represented_document_count,
                    row.coverage_truncated,
                )
            ):
                evidence_errors.append("coverage_mismatch")
        for request in observed.answer_requests:
            if tuple(s.section_id for s in request.evidence) != ids:
                evidence_errors.append("evidence_mismatch")
            if (
                request.rewritten_query != rewrite.query
                or request.search_context is None
                or request.search_context.search_scope != scope
            ):
                rewrite_errors.append("scope_mismatch")
        if not ids and observed.answer_requests:
            execution_errors.append("budget_exceeded")
    elif observed.selected_sections or observed.answer_requests:
        execution_errors.append("budget_exceeded")
    result = observed.result
    if result is not None:
        if result.kind not in turn.expected.result_kinds:
            publication_errors.append("disposition_mismatch")
        selected = {s.section_id: s for s in observed.selected_sections}
        cited = {citation.section_id for citation in result.citations}
        if result.kind == "answer":
            if (
                not cited
                or not cited <= set(selected)
                or not set(turn.expected.required_citations) <= cited
            ):
                publication_errors.append("citation_mismatch")
            if any(
                c.section_id in selected
                and (
                    c.document_id != selected[c.section_id].document_id
                    or c.corpus_version != selected[c.section_id].corpus_version
                )
                for c in result.citations
            ):
                publication_errors.append("citation_mismatch")
            if turn.expected.require_scope_note and not result.text.endswith(OVERVIEW_SCOPE_NOTE):
                publication_errors.append("scope_note_missing")
        elif result.citations:
            publication_errors.append("citation_mismatch")
        if len(result.text) > 8000:
            execution_errors.append("budget_exceeded")
    return TurnVerdict(
        rewrite=_verdict(rewrite_errors, ran=bool(observed.rewrite_requests)),
        retrieval=_verdict(evidence_errors, ran=isinstance(rewrite, SearchRewrite)),
        publication=_verdict(publication_errors, ran=result is not None),
        execution=_verdict(execution_errors),
    )
