"""Exercise the retained selectors and reject misleading comparison bookkeeping."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from veritycx.knowledge.category_retrieval import select_scoped_evidence
from veritycx.knowledge.retrieval import RetrievalSelection

if TYPE_CHECKING:
    from veritycx.service.retrieval_comparison import ComparisonReport


@pytest.fixture(scope="module")
def measured() -> ComparisonReport:
    """Run the full component inventory once with real verified language resources."""
    from veritycx.service.retrieval_comparison import compare_retrieval

    return compare_retrieval(repetitions=2)


def test_all_inputs_and_exclusions_remain_visible(measured: ComparisonReport) -> None:
    """Missing probes and clarification turns must not quietly become passing retrieval cases."""
    assert len(measured.rows) == 144
    assert len(measured.exclusions) == 14
    assert sum(e.reason == "no_raw_probe" for e in measured.exclusions) == 12
    assert sum(e.reason == "authored_clarification" for e in measured.exclusions) == 2
    for version in ("v1", "v2", "v3"):
        assert sum(r.version == version and r.track == "raw" for r in measured.rows) == 19
        assert (
            sum(r.version == version and r.track == "scripted_rewrite" for r in measured.rows) == 29
        )
    assert measured.passed
    assert measured.provider_requests == 0 and measured.cost is None
    assert (
        measured.provenance.corpus_hash
        == "327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c"
    )
    assert measured.provenance.repetitions == 2
    assert "What cards does" not in measured.model_dump_json()


def test_real_original_cards_comparison_records_coverage_and_paired_outcomes(
    measured: ComparisonReport,
) -> None:
    """The measured result must come from actual v3 category selection, not its gold set."""
    current = next(
        r
        for r in measured.rows
        if r.version == "v3" and r.track == "raw" and r.case_id == "broad-cards-original"
    )
    assert set(current.selected_document_ids) == {"policy-03", "policy-08", "policy-16"}
    assert current.metrics is not None and current.uncached_passage_ms is not None
    assert current.metrics.allowed_document_precision == 1
    assert current.metrics.allowed_document_coverage == 1
    assert len(current.warm_samples_ms) == 2
    assert current.uncached_passage_ms >= 0
    assert any(p.improved > 0 for p in measured.pairs if p.baseline == "v1")


def test_unknowns_and_repetitions_cannot_inflate_quality_denominators(
    measured: ComparisonReport,
) -> None:
    """Timing repeats are samples, not additional independent gold questions."""
    group = next(
        g for g in measured.groups if g.version == "v3" and g.track == "raw" and g.family == "all"
    )
    assert group.input_count == 19
    assert group.assessed_count == 17 and group.unassessed_count == 2
    assert group.metrics["allowed_document_precision"].sample_count == 5
    assert group.warm_timing is not None and group.warm_timing.sample_count == 38
    unsupported = next(
        g
        for g in measured.groups
        if g.version == "v3" and g.track == "raw" and g.family == "unsupported"
    )
    assert unsupported.input_count == 4 and unsupported.assessed_count == 2
    assert unsupported.unsupported_nonempty_count > 0


@pytest.mark.parametrize("repetitions", [0, 21, True])
def test_invalid_repetitions_fail_before_execution(repetitions: int) -> None:
    """Invalid repeat budgets cannot start an unbounded benchmark."""
    from veritycx.service.retrieval_comparison import compare_retrieval

    with pytest.raises(ValueError, match="invalid_comparison_repetitions"):
        compare_retrieval(repetitions=repetitions)


def test_invalid_case_selection_fails_before_execution() -> None:
    """Unknown or duplicated catalog selections cannot silently alter the sample set."""
    from veritycx.service.retrieval_comparison import compare_retrieval

    for ids in (["unknown"], ["broad-cards-original"] * 2, []):
        with pytest.raises(ValueError, match="invalid_regression_selection"):
            compare_retrieval(case_ids=ids, repetitions=1)


@pytest.mark.parametrize("fault", ["body", "unknown", "exception", "unstable"])
def test_failed_or_corrupt_selector_cannot_disappear_from_comparison(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Correct canned IDs, thrown errors and unstable samples cannot produce success."""
    import veritycx.service.retrieval_comparison as comparison

    original = select_scoped_evidence
    calls = 0

    def corrupt(*args: object, **kwargs: object) -> RetrievalSelection:
        nonlocal calls
        calls += 1
        if fault == "exception":
            raise RuntimeError("PRIVATE_ERROR_CANARY")
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        if fault == "unstable" and calls % 2 == 0:
            return replace(result, sections=())
        field = "section_id" if fault == "unknown" else "content"
        if fault != "unstable":
            return replace(
                result,
                sections=tuple(
                    s.model_copy(update={field: "PRIVATE_BODY_CANARY"}) for s in result.sections
                ),
            )
        return result

    monkeypatch.setattr(comparison, "select_scoped_evidence", corrupt)
    report = comparison.compare_retrieval(case_ids=["broad-cards-original"], repetitions=1)
    assert not report.passed and len(report.rows) == 6
    assert sum(r.error is not None for r in report.rows) == 2
    assert all(r.error is None for r in report.rows if r.version != "v3")
    encoded = report.model_dump_json()
    assert "PRIVATE_" not in encoded


def test_latency_statistics_use_literal_nearest_rank_samples() -> None:
    """A percentile-index regression is observable without timing a machine."""
    from veritycx.service.retrieval_comparison import latency_stats

    stats = latency_stats([1.0, 2.0, 3.0, 4.0])
    assert stats is not None
    assert stats.sample_count == 4 and stats.median_ms == 2.5 and stats.p95_ms == 4
    assert latency_stats([]) is None


def test_changed_input_bytes_cannot_receive_a_different_provenance_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing fixture bytes during selection must reject the comparison, not mislabel it."""
    import veritycx.service.retrieval_cases as cases
    import veritycx.service.retrieval_comparison as comparison

    path = tmp_path / "cases.json"
    path.write_bytes(cases.CASES_PATH.read_bytes())
    monkeypatch.setattr(cases, "CASES_PATH", path)
    monkeypatch.setattr(comparison, "CASES_PATH", path)

    def mutate(*args: object, **kwargs: object) -> RetrievalSelection:
        result = select_scoped_evidence(*args, **kwargs)  # type: ignore[arg-type]
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(comparison, "select_scoped_evidence", mutate)
    with pytest.raises(ValueError, match="comparison_inputs_changed"):
        comparison.compare_retrieval(case_ids=["broad-cards-original"], repetitions=1)
