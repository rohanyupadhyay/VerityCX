"""Publish bounded verdict metadata and private synthetic semantic-review material."""

import json
import os
import re
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from veritycx import PROJECT_ROOT
from veritycx.conversations.models import ClosedModel, VersionedModel
from veritycx.knowledge.scope import CategoryCoverage, SearchScope
from veritycx.providers.protocol import Usage
from veritycx.providers.rewrite import SearchRewrite
from veritycx.service.retrieval_cases import Identifier, RegressionError, load_cases
from veritycx.service.retrieval_checks import RegressionRun, TurnVerdict

EVIDENCE_ROOT = PROJECT_ROOT / ".cache/support/evidence/retrieval-regressions"
SourceId = Annotated[str, Field(pattern=r"^(?:policy-[0-9]{2}|conflict-[0-9]{2}-[ab]):[0-9]{4}$")]
ModelName = Annotated[str, Field(max_length=128, pattern=r"^[a-zA-Z0-9._:/-]+$")]


class Provenance(ClosedModel):
    """Allowlist reproducibility fields rather than serializing arbitrary metadata."""

    corpus_version: str = Field(max_length=100, pattern=r"^synthetic-[a-f0-9]{64}$")
    corpus_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    ranking_version: Literal[3]
    nlp_policy_version: int = Field(ge=1)
    rewrite_prompt_version: Literal[2]
    answer_prompt_version: Literal[3]
    configured_answer_model: ModelName | None = None
    configured_rewrite_model: ModelName | None = None


class PublicTurn(ClosedModel):
    """Exclude original text, rewritten query and provider request bodies."""

    turn_id: Identifier
    result_kind: (
        Literal["answer", "clarify", "abstain", "error", "unavailable", "escalation"] | None
    )
    verdict: TurnVerdict
    selected_source_ids: tuple[SourceId, ...] = Field(max_length=40)
    cited_source_ids: tuple[SourceId, ...] = Field(max_length=40)
    scope: SearchScope | None
    coverage: CategoryCoverage | None
    rewrite_calls: int = Field(ge=0, le=100)
    answer_calls: int = Field(ge=0, le=100)
    answer_attempts: int = Field(ge=0, le=100)
    rewrite_model: ModelName | None
    answer_models: tuple[ModelName | None, ...] = Field(max_length=4)
    usage: tuple[Usage | None, ...] = Field(max_length=4)
    elapsed_ms: int = Field(ge=0)


class PublicScenario(ClosedModel):
    """Keep every selected scenario and ordered turn visible in the result."""

    case_id: Identifier
    turns: tuple[PublicTurn, ...] = Field(min_length=1, max_length=4)


class PublicSummary(VersionedModel):
    """Reject accidental raw child output or incomplete successful summaries."""

    suite: Literal["retrieval-regressions"] = "retrieval-regressions"
    report_id: str
    mode: Literal["offline", "live"]
    evidence_kind: Literal["scripted", "live"]
    automated_passed: bool
    human_review: Literal["pending"] = "pending"
    scenario_count: int = Field(ge=0, le=24)
    turn_count: int = Field(ge=0, le=31)
    provider_requests: int = Field(ge=0, le=3100)
    cost: None = None
    provenance: Provenance
    scenarios: tuple[PublicScenario, ...] = Field(max_length=24)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        """Counts and success cannot disagree with the visible per-turn verdicts."""
        if str(UUID(self.report_id)) != self.report_id:
            raise ValueError("invalid_report_identity")
        turns = [turn for case in self.scenarios for turn in case.turns]
        passed = bool(self.scenarios) and all(turn.verdict.passed for turn in turns)
        if (
            self.scenario_count != len(self.scenarios)
            or self.turn_count != len(turns)
            or self.automated_passed != passed
            or self.provider_requests != sum(t.rewrite_calls + t.answer_calls for t in turns)
            or self.evidence_kind != ("live" if self.mode == "live" else "scripted")
        ):
            raise ValueError("inconsistent_regression_summary")
        if len({case.case_id for case in self.scenarios}) != len(self.scenarios) or any(
            len({turn.turn_id for turn in case.turns}) != len(case.turns) for case in self.scenarios
        ):
            raise ValueError("duplicate_regression_summary")
        return self


def _model(value: object) -> str | None:
    """Bound model labels and refuse credential-shaped accidental metadata."""
    return (
        value
        if isinstance(value, str)
        and len(value) <= 128
        and not value.startswith("sk-")
        and re.fullmatch(r"[a-zA-Z0-9._:/-]+", value)
        else None
    )


def public_summary(run: RegressionRun) -> dict[str, object]:
    """Construct a new allowlisted object instead of dumping captured requests."""
    scenarios = []
    for case in run.scenarios:
        turns = []
        for observed, verdict in case.turns:
            rewrite = observed.rewrite.result if observed.rewrite else None
            row = observed.rewrite_row
            coverage = None
            if row and row.search_scope == "category_overview":
                try:
                    coverage = CategoryCoverage.model_validate(
                        {
                            "eligible_document_count": row.eligible_document_count,
                            "represented_document_count": row.represented_document_count,
                            "coverage_truncated": row.coverage_truncated,
                        }
                    )
                except ValueError:
                    pass
            turns.append(
                PublicTurn(
                    turn_id=observed.turn_id,
                    result_kind=observed.result.kind if observed.result else None,
                    verdict=verdict,
                    selected_source_ids=tuple(s.section_id for s in observed.selected_sections),
                    cited_source_ids=tuple(c.section_id for c in observed.result.citations)
                    if observed.result
                    else (),
                    scope=rewrite.search_scope() if isinstance(rewrite, SearchRewrite) else None,
                    coverage=coverage,
                    rewrite_calls=len(observed.rewrite_requests),
                    answer_calls=len(observed.answer_requests),
                    answer_attempts=observed.answer_attempts,
                    rewrite_model=_model(observed.rewrite.model) if observed.rewrite else None,
                    answer_models=tuple(
                        _model(r.model) if r else None for r in observed.answer_results
                    ),
                    usage=tuple(
                        (
                            [observed.rewrite.usage]
                            if observed.rewrite
                            else [None] * len(observed.rewrite_requests)
                        )
                        + [r.usage if r else None for r in observed.answer_results]
                    ),
                    elapsed_ms=observed.elapsed_ms,
                )
            )
        scenarios.append(PublicScenario(case_id=case.case_id, turns=tuple(turns)))
    metadata = {name: run.metadata.get(name) for name in Provenance.model_fields}
    for name in ("configured_answer_model", "configured_rewrite_model"):
        metadata[name] = _model(metadata[name])
    summary = PublicSummary(
        report_id=str(run.metadata["run_id"]),
        mode=run.mode,
        evidence_kind="live" if run.mode == "live" else "scripted",
        automated_passed=run.passed,
        scenario_count=len(scenarios),
        turn_count=sum(len(c.turns) for c in scenarios),
        provider_requests=sum(t.rewrite_calls + t.answer_calls for c in scenarios for t in c.turns),
        provenance=Provenance.model_validate(metadata),
        scenarios=tuple(scenarios),
    )
    return summary.model_dump(mode="json")


def exit_status(summary: dict[str, object]) -> int:
    """A live structural pass deliberately retains pending semantic acceptance."""
    value = PublicSummary.model_validate_json(json.dumps(summary))
    return (2 if value.mode == "live" else 0) if value.automated_passed else 1


def write_review_report(run: RegressionRun) -> Path:
    """Write only private synthetic review fields to a fresh owned directory."""
    summary = public_summary(run)
    report_id = str(UUID(str(summary["report_id"])))
    root = EVIDENCE_ROOT
    if not root.is_relative_to(PROJECT_ROOT) or not root.resolve().is_relative_to(
        PROJECT_ROOT.resolve()
    ):
        raise RegressionError("invalid_regression_report_root")
    cursor = root
    while cursor != PROJECT_ROOT:
        if cursor.is_symlink():
            raise RegressionError("invalid_regression_report_root")
        cursor = cursor.parent
    directory = root / report_id
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.mkdir(mode=0o700)
    except OSError:
        raise RegressionError("regression_report_unavailable") from None
    cases = {case.id: case for case in load_cases().scenarios}
    details = []
    for case in run.scenarios:
        gold = {turn.id: turn for turn in cases[case.case_id].turns}
        for observed, verdict in case.turns:
            details.append(
                {
                    "case_id": case.case_id,
                    "turn_id": observed.turn_id,
                    "question": gold[observed.turn_id].question,
                    "expected_facts": gold[observed.turn_id].expected.required_facts,
                    "rewrite_requests": [
                        {"question": r.question, "context": [m.model_dump() for m in r.context]}
                        for r in observed.rewrite_requests
                    ],
                    "rewrite": observed.rewrite.result.model_dump(mode="json")
                    if observed.rewrite
                    else None,
                    "result": observed.result.model_dump(mode="json") if observed.result else None,
                    "answer_results": [
                        result.model_dump(mode="json") if result else None
                        for result in observed.answer_results
                    ],
                    "selected_source_ids": [s.section_id for s in observed.selected_sections],
                    "verdict": verdict.model_dump(mode="json"),
                    "execution_failed": bool(observed.execution_error),
                }
            )
    path = directory / "review.json"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"summary": summary, "turns": details}, output, ensure_ascii=False, indent=2)
    except OSError:
        raise RegressionError("regression_report_unavailable") from None
    return path
