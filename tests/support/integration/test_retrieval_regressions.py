"""Run the authored quality inventory through actual fenced worker execution."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path

import pytest

from veritycx.knowledge.category_retrieval import select_scoped_evidence
from veritycx.knowledge.configuration import active_corpus
from veritycx.knowledge.retrieval import RetrievalSelection
from veritycx.orchestration import graph
from veritycx.persistence.database import database_pool
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_all_regression_scenarios_use_real_pipeline(test_database_url: str) -> None:
    """The real graph preserves coverage, context and publication over all 31 turns."""
    from veritycx.service.retrieval_cases import load_cases, load_replays
    from veritycx.service.retrieval_providers import replay_provider_factory
    from veritycx.service.retrieval_runner import exercise_regressions

    async def exercise() -> None:
        manifest, evidence = active_corpus("synthetic")
        cases = load_cases()
        async with database_pool(test_database_url) as pool:
            result = await exercise_regressions(
                pool,
                Settings(),
                cases.scenarios,
                manifest=manifest,
                evidence=evidence,
                providers=replay_provider_factory(load_replays(cases, manifest)),
                mode="offline",
            )
        failures = {
            case.case_id: [verdict.model_dump() for _, verdict in case.turns if not verdict.passed]
            for case in result.scenarios
            if not all(v.passed for _, v in case.turns)
        }
        assert result.passed, json.dumps(failures)
        assert len(result.scenarios) == 24
        assert sum(len(case.turns) for case in result.scenarios) == 31
        original = next(case for case in result.scenarios if case.case_id == "broad-cards-original")
        assert {s.document_id for s in original.turns[0][0].selected_sections} == {
            "policy-03",
            "policy-08",
            "policy-16",
        }
        assert all(
            len(o.rewrite_requests) == 1 and o.answer_attempts <= 2
            for case in result.scenarios
            for o, _ in case.turns
        )
        interleaved = next(c for c in result.scenarios if c.case_id == "followup-interleaved")
        assert (
            interleaved.turns[2][0].rewrite_requests[0].context[0].text
            == "What is the Cedar card replacement fee?"
        )
        assert (
            interleaved.turns[3][0].rewrite_requests[0].context[0].text
            == "What is the Hazel card foreign fee?"
        )

    run_async(exercise())


@pytest.mark.parametrize("stage", ["create", "accept", "claim", "observe"])
def test_storage_failure_keeps_prior_results_and_unaffected_conversations(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str
) -> None:
    """A single failed storage operation cannot discard paid calls or stop independent cases."""
    import veritycx.service.retrieval_reports as reports
    import veritycx.service.retrieval_runner as runner
    from veritycx.persistence.repository import Repository
    from veritycx.service.retrieval_cases import load_cases, load_replays
    from veritycx.service.retrieval_providers import replay_provider_factory

    target = runner if stage == "observe" else Repository
    name = "_observe" if stage == "observe" else stage
    original_operation: Callable[..., Awaitable[object]] = getattr(target, name)
    calls = 0

    async def fail_once(*args: object, **kwargs: object) -> object:
        """Inject one storage-boundary failure after a complete successful scenario."""
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("PRIVATE_STORAGE_FAILURE_CANARY")
        return await original_operation(*args, **kwargs)

    monkeypatch.setattr(target, name, fail_once)
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(reports, "EVIDENCE_ROOT", tmp_path / "reports")

    async def exercise() -> None:
        manifest, evidence = active_corpus("synthetic")
        cases = load_cases()
        by_id = {case.id: case for case in cases.scenarios}
        selected = tuple(
            by_id[name]
            for name in ("plural-cedar-card", "followup-interleaved", "broad-cards-original")
        )
        async with database_pool(test_database_url) as pool:
            result = await runner.exercise_regressions(
                pool,
                Settings(),
                selected,
                manifest=manifest,
                evidence=evidence,
                providers=replay_provider_factory(load_replays(cases, manifest)),
                mode="offline",
            )
        assert not result.passed
        assert [case.case_id for case in result.scenarios] == [case.id for case in selected]
        first, interleaved, last = result.scenarios
        assert first.turns[0][1].passed and last.turns[0][1].passed
        failed, independent, dependent, independent_followup = interleaved.turns
        assert failed[1].execution.status == "fail"
        assert independent[1].passed and independent_followup[1].passed
        assert dependent[1].execution.reasons == ("dependency_failed",)
        assert dependent[1].rewrite.status == "not_run"
        observation = failed[0]
        assert len(observation.rewrite_requests) == (1 if stage == "observe" else 0)
        assert len(observation.answer_requests) == (1 if stage == "observe" else 0)
        assert len(observation.answer_results) == (1 if stage == "observe" else 0)
        assert observation.answer_attempts == len(observation.answer_requests)
        summary = reports.public_summary(result)
        assert summary["scenario_count"] == 3 and summary["turn_count"] == 6
        assert summary["provider_requests"] == (10 if stage == "observe" else 8)
        private = reports.write_review_report(result).read_text()
        assert "PRIVATE_STORAGE_FAILURE_CANARY" not in private + json.dumps(summary)

    run_async(exercise())


@pytest.mark.parametrize("fault", ["missing_pine", "lost_history", "wrong_body"])
def test_runner_detects_pipeline_faults_despite_scripted_answers(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Intentionally broken stage wiring must make the quality run fail."""
    from veritycx.service.retrieval_cases import load_cases, load_replays, select_cases
    from veritycx.service.retrieval_providers import replay_provider_factory
    from veritycx.service.retrieval_runner import exercise_regressions

    original = select_scoped_evidence

    def missing(*args: object, **kwargs: object) -> RetrievalSelection:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        if fault == "wrong_body":
            return replace(
                result,
                sections=tuple(
                    s.model_copy(update={"content": "A changed policy body."})
                    for s in result.sections
                ),
            )
        return replace(
            result, sections=tuple(s for s in result.sections if s.document_id != "policy-16")
        )

    if fault != "lost_history":
        monkeypatch.setattr(graph, "select_scoped_evidence", missing)
    else:
        monkeypatch.setattr(graph, "recent_context", lambda _: ())

    async def exercise() -> None:
        manifest, evidence = active_corpus("synthetic")
        cases = load_cases()
        selected = ["followup-interleaved"] if fault == "lost_history" else ["broad-cards-original"]
        async with database_pool(test_database_url) as pool:
            result = await exercise_regressions(
                pool,
                Settings(),
                select_cases(cases, selected),
                manifest=manifest,
                evidence=evidence,
                providers=replay_provider_factory(load_replays(cases, manifest)),
                mode="offline",
            )
        assert not result.passed
        labels = [
            reason
            for case in result.scenarios
            for _, verdict in case.turns
            for boundary in (
                verdict.rewrite,
                verdict.retrieval,
                verdict.publication,
                verdict.execution,
            )
            for reason in boundary.reasons
        ]
        assert {
            "missing_pine": "missing_evidence",
            "lost_history": "history_mismatch",
            "wrong_body": "evidence_mismatch",
        }[fault] in labels

    run_async(exercise())
