"""Load bounded authored regression inputs separately from offline provider replays."""

import json
from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from veritycx import PROJECT_ROOT
from veritycx.conversations.models import ClosedModel, VersionedModel, parse_json
from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.models import CorpusManifest
from veritycx.knowledge.scope import CategoryCoverage, SearchScope
from veritycx.providers.protocol import ProviderResult
from veritycx.providers.rewrite import RewriteResult

CASES_PATH = PROJECT_ROOT / "tests/support/fixtures/retrieval-regressions.json"
REPLAYS_PATH = PROJECT_ROOT / "tests/support/fixtures/retrieval-replays.json"
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")]


class RegressionError(ValueError):
    """Expose only fixed validation categories, never fixture or credential content."""


def _distinct(values: Sequence[object]) -> None:
    """Reject duplicate declarations without requiring hashable nested models."""
    if any(value in values[:index] for index, value in enumerate(values)):
        raise ValueError("duplicate_regression_value")


class EvidenceExpectation(ClosedModel):
    """Declare gold source membership independently of the selector's output."""

    required_documents: tuple[str, ...] = Field(default=(), max_length=40)
    allowed_documents: tuple[str, ...] | None = Field(default=None, max_length=40)
    forbidden_documents: tuple[str, ...] = Field(default=(), max_length=40)
    required_sections: tuple[str, ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        """Reject contradictory sets instead of creating impossible assertions."""
        for values in (self.required_documents, self.forbidden_documents, self.required_sections):
            _distinct(values)
        if self.allowed_documents is not None:
            _distinct(self.allowed_documents)
            if not set(self.required_documents) <= set(self.allowed_documents):
                raise ValueError("inconsistent_regression_evidence")
        if set(self.required_documents) & set(self.forbidden_documents):
            raise ValueError("inconsistent_regression_evidence")
        return self


class RetrievalProbe(ClosedModel):
    """Apply an explicitly authored scope to raw wording, without a model rewrite."""

    scope: SearchScope
    expected: EvidenceExpectation
    empty: bool | None = None


class TurnExpectation(ClosedModel):
    """Describe permitted outcomes rather than exact model-authored wording."""

    rewrite_kinds: tuple[Literal["search", "clarify"], ...] = Field(min_length=1, max_length=2)
    scopes: tuple[SearchScope, ...] = Field(max_length=6)
    result_kinds: tuple[Literal["answer", "clarify", "abstain"], ...] = Field(
        min_length=1, max_length=3
    )
    evidence: EvidenceExpectation
    required_citations: tuple[str, ...] = Field(default=(), max_length=6)
    coverage: CategoryCoverage | None = None
    minimum_category_documents: dict[CategoryKey, Annotated[int, Field(ge=0, le=6)]] = Field(
        default_factory=dict
    )
    require_scope_note: bool = False
    required_facts: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        """Require a usable search scope and unique bounded outcome declarations."""
        for values in (self.rewrite_kinds, self.scopes, self.result_kinds, self.required_citations):
            _distinct(values)
        if ("search" in self.rewrite_kinds) != bool(self.scopes):
            raise ValueError("inconsistent_regression_scope")
        if any(not fact.strip() or len(fact) > 8000 for fact in self.required_facts):
            raise ValueError("invalid_regression_fact")
        return self


class RegressionTurn(ClosedModel):
    """Bind a question and independent expected behavior to a local conversation alias."""

    id: Identifier
    conversation: Identifier
    question: str = Field(min_length=1, max_length=8000)
    expected: TurnExpectation
    probe: RetrievalProbe | None = None

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        """Reject a whitespace-only question before any accepted turn is created."""
        if not self.question.strip():
            raise ValueError("invalid_regression_question")
        return self


class RegressionScenario(ClosedModel):
    """Keep interleaved conversations explicit and isolated inside each scenario."""

    id: Identifier
    family: Literal["plurals", "paraphrases", "broad", "followups", "unsupported"]
    conversations: tuple[Identifier, ...] = Field(min_length=1, max_length=2)
    turns: tuple[RegressionTurn, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_turns_and_aliases(self) -> Self:
        """Reject undeclared/unused aliases and ambiguous replay keys."""
        _distinct(self.conversations)
        _distinct(tuple(turn.id for turn in self.turns))
        if {turn.conversation for turn in self.turns} != set(self.conversations):
            raise ValueError("invalid_regression_conversations")
        return self


class RegressionSet(VersionedModel):
    """Cap execution before allocating storage or making a paid request."""

    provenance: str
    scenarios: tuple[RegressionScenario, ...] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def bounded_inventory(self) -> Self:
        """Enforce the global 31-turn/93-request ceiling without silent truncation."""
        _distinct(tuple(case.id for case in self.scenarios))
        if sum(len(case.turns) for case in self.scenarios) > 31:
            raise ValueError("regression_turn_limit")
        return self


class ReplayTurn(ClosedModel):
    """Contain only authored offline outputs, never an expectation evaluator."""

    case_id: Identifier
    turn_id: Identifier
    rewrite: RewriteResult
    answer: ProviderResult | None
    available_claims_only: bool = False

    @model_validator(mode="after")
    def offline_identity(self) -> Self:
        """Prevent scripted outputs from being mislabeled as observed live output."""
        if self.rewrite.model != "scripted-rewrite-v1" or (
            self.answer is not None and self.answer.model != "scripted-answer-v1"
        ):
            raise ValueError("invalid_replay_identity")
        if self.rewrite.result.disposition == "clarify" and self.answer is not None:
            raise ValueError("unexpected_replay_answer")
        if self.available_claims_only and (
            self.answer is None or self.answer.disposition != "answer"
        ):
            raise ValueError("invalid_replay_candidates")
        return self


class ReplaySet(VersionedModel):
    """Validate one bounded set of replay records before indexing its keys."""

    turns: tuple[ReplayTurn, ...] = Field(min_length=1, max_length=31)


def load_cases() -> RegressionSet:
    """Load only the fixed authored catalog, sanitizing parse failures."""
    try:
        return RegressionSet.model_validate_json(json.dumps(parse_json(CASES_PATH.read_bytes())))
    except (OSError, ValueError):
        raise RegressionError("invalid_regression_cases") from None


def select_cases(
    cases: RegressionSet, case_ids: Sequence[str] | None
) -> tuple[RegressionScenario, ...]:
    """Select a unique nonempty subset in stable inventory order."""
    if case_ids is None:
        return cases.scenarios
    selected = set(case_ids)
    if (
        not selected
        or len(selected) != len(case_ids)
        or not selected <= {case.id for case in cases.scenarios}
    ):
        raise RegressionError("invalid_regression_selection")
    return tuple(case for case in cases.scenarios if case.id in selected)


def validate_case_sources(cases: RegressionSet, manifest: CorpusManifest) -> None:
    """Check every gold reference against source identity, not observed retrieval."""
    documents = {entry.document_id for entry in manifest.entries}
    sections = {identifier for entry in manifest.entries for identifier in entry.section_ids}
    for case in cases.scenarios:
        for turn in case.turns:
            expectations = [turn.expected.evidence]
            if turn.probe is not None:
                expectations.append(turn.probe.expected)
            if not set(turn.expected.required_citations) <= sections:
                raise RegressionError("invalid_regression_source")
            for item in expectations:
                if (
                    not set(
                        item.required_documents
                        + item.forbidden_documents
                        + (item.allowed_documents or ())
                    )
                    <= documents
                    or not set(item.required_sections) <= sections
                ):
                    raise RegressionError("invalid_regression_source")


def load_replays(
    cases: RegressionSet, manifest: CorpusManifest
) -> dict[tuple[str, str], ReplayTurn]:
    """Load offline data only when requested, rejecting missing or duplicate keys."""
    try:
        records = ReplaySet.model_validate_json(json.dumps(parse_json(REPLAYS_PATH.read_bytes())))
        values = {(item.case_id, item.turn_id): item for item in records.turns}
        expected = {(case.id, turn.id) for case in cases.scenarios for turn in case.turns}
        sections = {identifier for entry in manifest.entries for identifier in entry.section_ids}
        if len(values) != len(records.turns) or set(values) != expected:
            raise ValueError("invalid_replay_keys")
        for item in values.values():
            if item.answer is not None and any(
                not set(claim.evidence_ids) <= sections for claim in item.answer.claims
            ):
                raise ValueError("invalid_replay_source")
        return values
    except (OSError, ValueError):
        raise RegressionError("invalid_regression_replays") from None
