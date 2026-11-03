"""Compare retained retrieval components on frozen, explicitly supplied offline inputs."""

import hashlib
import math
import platform
import shutil
import statistics
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Literal, Self
from uuid import uuid4

from pydantic import model_validator

from veritycx import PROJECT_ROOT
from veritycx.conversations.models import ClosedModel, VersionedModel
from veritycx.knowledge.category_retrieval import select_scoped_evidence
from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import build_manifest, load_sections
from veritycx.knowledge.models import CatalogEntry, CorpusManifest, EvidenceSection
from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.retrieval import RetrievalSelection, retrieve, select_evidence
from veritycx.knowledge.scope import SearchScope
from veritycx.knowledge.synonyms import WordNetExpander
from veritycx.providers.rewrite import SearchRewrite
from veritycx.service.retrieval_cases import (
    CASES_PATH,
    REPLAYS_PATH,
    Identifier,
    RegressionError,
    RegressionScenario,
    RegressionTurn,
    load_cases,
    load_replays,
    select_cases,
    validate_case_sources,
)
from veritycx.service.retrieval_metrics import EvidenceMetrics, assess_evidence

Version = Literal["v1", "v2", "v3"]
Track = Literal["raw", "scripted_rewrite"]
Family = Literal["plurals", "paraphrases", "broad", "followups", "unsupported"]
ExecutionError = Literal["selection_failed", "invalid_selection", "nondeterministic_selection"]
VERSIONS: tuple[Version, ...] = ("v1", "v2", "v3")
METRICS = (
    "required_document_recall",
    "required_document_rr",
    "allowed_document_precision",
    "allowed_document_coverage",
)
MODULES = (
    "knowledge/retrieval.py",
    "knowledge/category_retrieval.py",
    "knowledge/nlp.py",
    "knowledge/synonyms.py",
    "service/retrieval_metrics.py",
    "service/retrieval_comparison.py",
    "service/retrieval_checks.py",
    "service/retrieval_cases.py",
    "knowledge/catalog.py",
    "knowledge/manifest.py",
    "knowledge/models.py",
    "knowledge/resources.py",
    "knowledge/scope.py",
)


class TimingStats(ClosedModel):
    """Describe actual samples without implying production latency or statistical confidence."""

    sample_count: int
    median_ms: float
    p95_ms: float


def latency_stats(samples: Sequence[float]) -> TimingStats | None:
    """Use ordinary median and nearest-rank p95, with no invented empty sample."""
    if not samples:
        return None
    if any(not math.isfinite(x) or x < 0 for x in samples):
        raise RegressionError("invalid_comparison_timing")
    ordered = sorted(samples)
    return TimingStats(
        sample_count=len(samples),
        median_ms=statistics.median(samples),
        p95_ms=ordered[math.ceil(0.95 * len(samples)) - 1],
    )


class ComparisonRow(ClosedModel):
    """Retain every attempted variant without publishing input or source text."""

    case_id: Identifier
    turn_id: Identifier
    family: Family
    track: Track
    version: Version
    selected_source_ids: tuple[str, ...] = ()
    selected_document_ids: tuple[str, ...] = ()
    metrics: EvidenceMetrics | None = None
    expected_empty: bool | None = None
    uncached_passage_ms: float | None = None
    warm_samples_ms: tuple[float, ...] = ()
    error: ExecutionError | None = None


class ExcludedInput(ClosedModel):
    """Account for original inventory turns not applicable to an input track."""

    case_id: Identifier
    turn_id: Identifier
    track: Track
    reason: Literal["no_raw_probe", "authored_clarification"]


class MetricMean(ClosedModel):
    """Make each metric denominator explicit for partially labeled fixtures."""

    value: float | None
    sample_count: int


class GroupSummary(ClosedModel):
    """Keep quality case counts independent of the number of timing repetitions."""

    version: Version
    track: Track
    family: str
    input_count: int
    assessed_count: int
    passed_count: int
    unassessed_count: int
    error_count: int
    unsupported_nonempty_count: int
    explicit_empty_count: int
    explicit_empty_failed_count: int
    metrics: dict[str, MetricMean]
    uncached_timing: TimingStats | None
    warm_timing: TimingStats | None


class PairedSummary(ClosedModel):
    """Pair the same authored inputs; missing labels are excluded visibly."""

    track: Track
    baseline: Version
    improved: int
    regressed: int
    unchanged: int
    unassessed: int


class ComparisonProvenance(ClosedModel):
    """Pin inputs, metric implementation and machine context without environment values."""

    corpus_hash: str
    corpus_version: str
    fixture_sha256: str
    replay_sha256: str
    module_sha256: dict[str, str]
    resource_sha256: str
    git_revision: str | None
    working_tree_dirty: bool | None
    python_version: str
    platform: str
    repetitions: int
    shared_setup_ms: float


def _passed(rows: Sequence[ComparisonRow]) -> bool:
    """Earlier baseline quality failures are data; current and execution regressions fail."""
    return bool(rows) and all(
        row.error is None
        and not (row.version == "v3" and row.metrics and row.metrics.contract_passed is False)
        for row in rows
    )


class ComparisonReport(VersionedModel):
    """A component comparison cannot establish model or answer semantic acceptance."""

    suite: Literal["retrieval-comparison"] = "retrieval-comparison"
    evidence_kind: Literal["offline-components"] = "offline-components"
    input_policy: Literal["common_original_query_and_authored_scope"] = (
        "common_original_query_and_authored_scope"
    )
    timing_policy: Literal["shared_language_resources_separate_passage_caches_serial"] = (
        "shared_language_resources_separate_passage_caches_serial"
    )
    run_id: str
    started_at: str
    provider_requests: Literal[0] = 0
    usage: None = None
    cost: None = None
    provenance: ComparisonProvenance
    rows: tuple[ComparisonRow, ...]
    exclusions: tuple[ExcludedInput, ...]
    groups: tuple[GroupSummary, ...]
    pairs: tuple[PairedSummary, ...]
    passed: bool

    @model_validator(mode="after")
    def coherent(self) -> Self:
        """A persisted success flag must agree with every visible execution/current result."""
        if self.passed != _passed(self.rows):
            raise ValueError("invalid_comparison_outcome")
        return self


@dataclass(frozen=True)
class _Input:
    case: RegressionScenario
    turn: RegressionTurn
    track: Track
    query: str
    scope: SearchScope


@dataclass
class _Trial:
    normalizer: TextNormalizer
    expander: WordNetExpander
    first: RetrievalSelection | None = None
    uncached_ms: float | None = None
    samples: list[float] = field(default_factory=list)
    error: ExecutionError | None = None


def summarize_rows(rows: Sequence[ComparisonRow]) -> tuple[GroupSummary, ...]:
    """Aggregate only actual metric values, publishing their independent denominators."""
    summaries = []
    for version in VERSIONS:
        for track in ("raw", "scripted_rewrite"):
            members = [r for r in rows if r.version == version and r.track == track]
            for family in ("all", *sorted({r.family for r in members})):
                group = [r for r in members if family == "all" or r.family == family]
                if not group:
                    continue
                valid = [r for r in group if r.error is None and r.metrics is not None]
                metrics = {}
                for name in METRICS:
                    values = [
                        value for r in valid if (value := getattr(r.metrics, name)) is not None
                    ]
                    metrics[name] = MetricMean(
                        value=statistics.mean(values) if values else None, sample_count=len(values)
                    )
                assessed = [r for r in valid if r.metrics and r.metrics.contract_passed is not None]
                summaries.append(
                    GroupSummary(
                        version=version,
                        track=track,
                        family=family,
                        input_count=len(group),
                        assessed_count=len(assessed),
                        passed_count=sum(
                            bool(r.metrics and r.metrics.contract_passed) for r in assessed
                        ),
                        unassessed_count=sum(
                            bool(r.metrics and r.metrics.contract_passed is None) for r in valid
                        ),
                        error_count=sum(r.error is not None for r in group),
                        unsupported_nonempty_count=sum(
                            r.family == "unsupported" and bool(r.selected_source_ids) for r in valid
                        ),
                        explicit_empty_count=sum(r.expected_empty is not None for r in valid),
                        explicit_empty_failed_count=sum(
                            bool(r.metrics and "empty_mismatch" in r.metrics.reasons) for r in valid
                        ),
                        metrics=metrics,
                        uncached_timing=latency_stats(
                            [
                                r.uncached_passage_ms
                                for r in valid
                                if r.uncached_passage_ms is not None
                            ]
                        ),
                        warm_timing=latency_stats(
                            [value for r in valid for value in r.warm_samples_ms]
                        ),
                    )
                )
    return tuple(summaries)


def _pairs(rows: Sequence[ComparisonRow]) -> tuple[PairedSummary, ...]:
    values = {(r.track, r.case_id, r.turn_id, r.version): r for r in rows}
    result = []
    for track in ("raw", "scripted_rewrite"):
        current = [r for r in rows if r.track == track and r.version == "v3"]
        if not current:
            continue
        for baseline in ("v1", "v2"):
            improved = regressed = unchanged = unassessed = 0
            for row in current:
                old = values[(row.track, row.case_id, row.turn_id, baseline)]
                before = old.metrics.contract_passed if old.metrics else None
                after = row.metrics.contract_passed if row.metrics else None
                if before is None or after is None:
                    unassessed += 1
                elif before == after:
                    unchanged += 1
                elif after:
                    improved += 1
                else:
                    regressed += 1
            result.append(
                PairedSummary(
                    track=track,
                    baseline=baseline,
                    improved=improved,
                    regressed=regressed,
                    unchanged=unchanged,
                    unassessed=unassessed,
                )
            )
    return tuple(result)


def _select(
    version: Version,
    item: _Input,
    evidence: Sequence[EvidenceSection],
    catalog: Sequence[CatalogEntry],
    trial: _Trial,
) -> RetrievalSelection:
    if version == "v1":
        selected = tuple(retrieve(item.turn.question + "\n" + item.query, evidence))
        return RetrievalSelection(selected, "primary" if selected else "empty")
    if version == "v2":
        return select_evidence(
            item.turn.question,
            item.query,
            evidence,
            normalizer=trial.normalizer,
            expander=trial.expander,
        )
    return select_scoped_evidence(
        item.turn.question,
        item.query,
        evidence,
        search_scope=item.scope,
        catalog_index=catalog,
        normalizer=trial.normalizer,
        expander=trial.expander,
    )


def _measure(
    item: _Input,
    index: int,
    repetitions: int,
    evidence: Sequence[EvidenceSection],
    catalog: Sequence[CatalogEntry],
    shared: WordNetExpander,
) -> list[ComparisonRow]:
    approved = {s.section_id: s for s in evidence}
    trials = {}
    for version in VERSIONS:
        normalizer = TextNormalizer()
        trials[version] = _Trial(normalizer, WordNetExpander(normalizer, reader=shared.reader))
    for phase in range(-1, repetitions):
        offset = (index + phase + 1) % len(VERSIONS)
        for version in VERSIONS[offset:] + VERSIONS[:offset]:
            trial = trials[version]
            if trial.error:
                continue
            try:
                start = perf_counter_ns()
                selection = _select(version, item, evidence, catalog, trial)
                elapsed = (perf_counter_ns() - start) / 1_000_000
                if (
                    len(selection.sections) > 6
                    or len({s.section_id for s in selection.sections}) != len(selection.sections)
                    or sum(len(s.content) for s in selection.sections) > 12000
                    or any(approved.get(s.section_id) != s for s in selection.sections)
                ):
                    trial.error = "invalid_selection"
                elif phase == -1:
                    trial.first = selection
                    trial.uncached_ms = elapsed
                elif selection != trial.first:
                    trial.error = "nondeterministic_selection"
                else:
                    trial.samples.append(elapsed)
            except Exception:
                trial.error = "selection_failed"
    result = []
    probe = item.turn.probe
    expected = probe.expected if item.track == "raw" and probe else item.turn.expected.evidence
    for version, trial in trials.items():
        selected = trial.first.sections if trial.first else ()
        empty = probe.empty if item.track == "raw" and probe else None
        metrics = (
            assess_evidence(
                expected,
                selected,
                scope=item.scope,
                catalog_index=catalog,
                expected_empty=empty,
                expected_coverage=item.turn.expected.coverage,
                minimum_category_documents=item.turn.expected.minimum_category_documents,
            )
            if trial.error is None
            else None
        )
        result.append(
            ComparisonRow(
                case_id=item.case.id,
                turn_id=item.turn.id,
                family=item.case.family,
                track=item.track,
                version=version,
                selected_source_ids=tuple(s.section_id for s in selected),
                selected_document_ids=tuple(dict.fromkeys(s.document_id for s in selected)),
                metrics=metrics,
                expected_empty=empty,
                uncached_passage_ms=trial.uncached_ms,
                warm_samples_ms=tuple(trial.samples),
                error=trial.error,
            )
        )
    return result


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprints(root: Path) -> dict[str, str]:
    """Bind the loaded inputs and implementation, detecting concurrent edits during a run."""
    paths = {name: PROJECT_ROOT / "src/veritycx" / name for name in MODULES}
    paths.update(
        fixtures=CASES_PATH,
        replays=REPLAYS_PATH,
        resources=PROJECT_ROOT / "config/retrieval-resources.json",
    )
    paths.update({f"document:{p.name}": p for p in root.glob("*.json")})
    return {name: _digest(path) for name, path in paths.items()}


def _provenance(
    manifest: CorpusManifest, repetitions: int, setup_ms: float, fingerprints: dict[str, str]
) -> ComparisonProvenance:
    try:
        git = shutil.which("git")
        if git is None:
            raise OSError("git_unavailable")
        revision = subprocess.check_output(  # noqa: S603 - resolved executable, fixed read-only args.
            [git, "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        dirty = bool(
            subprocess.check_output(  # noqa: S603 - resolved executable, fixed read-only args.
                [git, "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        )
    except (OSError, subprocess.SubprocessError):
        revision = None
        dirty = None
    return ComparisonProvenance(
        corpus_hash=manifest.aggregate_hash,
        corpus_version=manifest.corpus_version,
        fixture_sha256=fingerprints["fixtures"],
        replay_sha256=fingerprints["replays"],
        module_sha256={name: fingerprints[name] for name in MODULES},
        resource_sha256=fingerprints["resources"],
        git_revision=revision,
        working_tree_dirty=dirty,
        python_version=platform.python_version(),
        platform=sys.platform,
        repetitions=repetitions,
        shared_setup_ms=setup_ms,
    )


def compare_retrieval(
    *, case_ids: Sequence[str] | None = None, repetitions: int = 5
) -> ComparisonReport:
    """Use verified synthetic sources directly; never prepare/approve a cache or open storage."""
    if (
        isinstance(repetitions, bool)
        or not isinstance(repetitions, int)
        or not 1 <= repetitions <= 20
    ):
        raise RegressionError("invalid_comparison_repetitions")
    root, _, pin = source_mode("synthetic", validation=True)
    fingerprints = _fingerprints(root)
    cases = load_cases()
    selected = select_cases(cases, case_ids)
    manifest = build_manifest(root, "synthetic", pin)
    evidence = load_sections(root, manifest)
    validate_case_sources(cases, manifest)
    replays = load_replays(cases, manifest)
    catalog = manifest.catalog_index
    if catalog is None:
        raise RegressionError("invalid_regression_corpus")
    started = datetime.now(UTC).isoformat()
    setup_start = perf_counter_ns()
    shared = WordNetExpander(TextNormalizer())
    setup_ms = (perf_counter_ns() - setup_start) / 1_000_000
    inputs = []
    excluded = []
    for case in selected:
        for turn in case.turns:
            if turn.probe:
                inputs.append(_Input(case, turn, "raw", turn.question, turn.probe.scope))
            else:
                excluded.append(
                    ExcludedInput(
                        case_id=case.id, turn_id=turn.id, track="raw", reason="no_raw_probe"
                    )
                )
            rewrite = replays[(case.id, turn.id)].rewrite.result
            if isinstance(rewrite, SearchRewrite):
                inputs.append(
                    _Input(case, turn, "scripted_rewrite", rewrite.query, rewrite.search_scope())
                )
            else:
                excluded.append(
                    ExcludedInput(
                        case_id=case.id,
                        turn_id=turn.id,
                        track="scripted_rewrite",
                        reason="authored_clarification",
                    )
                )
    rows = [
        row
        for index, item in enumerate(inputs)
        for row in _measure(item, index, repetitions, evidence, catalog, shared)
    ]
    if _fingerprints(root) != fingerprints:
        raise RegressionError("comparison_inputs_changed")
    return ComparisonReport(
        run_id=str(uuid4()),
        started_at=started,
        provenance=_provenance(manifest, repetitions, setup_ms, fingerprints),
        rows=tuple(rows),
        exclusions=tuple(excluded),
        groups=summarize_rows(rows),
        pairs=_pairs(rows),
        passed=_passed(rows),
    )
