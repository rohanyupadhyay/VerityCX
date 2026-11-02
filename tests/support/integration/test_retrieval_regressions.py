"""Run the authored quality inventory through actual fenced worker execution."""

import json
from dataclasses import replace

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


@pytest.mark.parametrize("fault", ["missing_pine", "lost_history"])
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
        return replace(
            result, sections=tuple(s for s in result.sections if s.document_id != "policy-16")
        )

    if fault == "missing_pine":
        monkeypatch.setattr(graph, "select_scoped_evidence", missing)
    else:
        monkeypatch.setattr(graph, "recent_context", lambda _: ())

    async def exercise() -> None:
        manifest, evidence = active_corpus("synthetic")
        cases = load_cases()
        selected = ["broad-cards-original"] if fault == "missing_pine" else ["followup-interleaved"]
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
        assert ("missing_evidence" if fault == "missing_pine" else "history_mismatch") in labels

    run_async(exercise())
