"""Keep detailed synthetic review evidence private and public verdicts content-free."""

import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from tests.support.unit.test_retrieval_regressions import overview
from veritycx.providers.protocol import ContextMessage
from veritycx.service.retrieval_checks import RegressionRun, ScenarioResult, judge_turn


def sample_run(*, mode: str = "offline", private_canaries: bool = False) -> RegressionRun:
    """Build a supported observation with independent gold and optional privacy canaries."""
    turn, observed, catalog = overview()
    verdict = judge_turn(turn, observed, expected_history=(), catalog_index=catalog)
    if private_canaries:
        assert observed.result is not None
        observed = replace(
            observed,
            result=observed.result.model_copy(update={"text": "ANSWER_CANARY"}),
            rewrite_requests=(
                observed.rewrite_requests[0].model_copy(
                    update={
                        "question": "QUESTION_CANARY",
                        "context": (ContextMessage(role="user", text="HISTORY_CANARY"),),
                    }
                ),
            ),
            selected_sections=tuple(
                s.model_copy(update={"content": "BODY_CANARY"}) for s in observed.selected_sections
            ),
            execution_error="EXCEPTION_CANARY",
        )
    return RegressionRun(
        mode="live" if mode == "live" else "offline",
        metadata={
            "run_id": str(uuid4()),
            "corpus_version": observed.selected_sections[0].corpus_version,
            "corpus_hash": "327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c",
            "ranking_version": 3,
            "nlp_policy_version": 2,
            "rewrite_prompt_version": 2,
            "answer_prompt_version": 3,
            "configured_answer_model": "gpt-4.1-mini-2025-04-14",
            "configured_rewrite_model": "gpt-4.1-mini-2025-04-14",
            "private": "KEY_CANARY DSN_CANARY",
        },
        scenarios=(ScenarioResult("broad-cards-original", ((observed, verdict),)),),
    )


def test_public_summary_omits_content_and_private_metadata() -> None:
    """Questions, histories, answers and unknown metadata cannot escape via stdout."""
    from veritycx.service.retrieval_reports import public_summary

    summary = public_summary(sample_run(private_canaries=True))
    encoded = json.dumps(summary)
    for value in (
        "QUESTION_CANARY",
        "HISTORY_CANARY",
        "ANSWER_CANARY",
        "BODY_CANARY",
        "EXCEPTION_CANARY",
        "KEY_CANARY",
        "DSN_CANARY",
    ):
        assert value not in encoded
    assert summary["human_review"] == "pending" and summary["evidence_kind"] == "scripted"
    assert summary["scenario_count"] == summary["turn_count"] == 1
    assert summary["cost"] is None


def test_review_report_is_private_nonoverwriting_and_useful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private artifact retains review material without dumping raw requests or errors."""
    from veritycx.service import retrieval_reports

    monkeypatch.setattr(retrieval_reports, "EVIDENCE_ROOT", tmp_path / "reports")
    monkeypatch.setattr(retrieval_reports, "PROJECT_ROOT", tmp_path)
    run = sample_run(private_canaries=True)
    path = retrieval_reports.write_review_report(run)
    data = path.read_text()
    assert all(
        value in data
        for value in ("QUESTION_CANARY", "HISTORY_CANARY", "ANSWER_CANARY", "expected_facts")
    )
    assert all(
        value not in data
        for value in ("BODY_CANARY", "EXCEPTION_CANARY", "KEY_CANARY", "DSN_CANARY")
    )
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(ValueError):
        retrieval_reports.write_review_report(run)
    assert path.read_text() == data


def test_report_cannot_escape_its_owned_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid report identity cannot overwrite a chosen filesystem path."""
    from veritycx.service import retrieval_reports

    monkeypatch.setattr(retrieval_reports, "EVIDENCE_ROOT", tmp_path / "reports")
    monkeypatch.setattr(retrieval_reports, "PROJECT_ROOT", tmp_path)
    run = sample_run()
    with pytest.raises(ValueError):
        retrieval_reports.write_review_report(
            replace(run, metadata={**run.metadata, "run_id": "../../escape"})
        )
    assert not (tmp_path / "escape").exists()


def test_failed_durable_observation_retains_actual_answer_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paid answer remains inspectable even when its committed result cannot be read."""
    from veritycx.service import retrieval_reports

    monkeypatch.setattr(retrieval_reports, "EVIDENCE_ROOT", tmp_path / "reports")
    monkeypatch.setattr(retrieval_reports, "PROJECT_ROOT", tmp_path)
    run = sample_run()
    observed, _ = run.scenarios[0].turns[0]
    observed = replace(observed, result=None, execution_error="observation_failed")
    turn, _, catalog = overview()
    verdict = judge_turn(turn, observed, expected_history=(), catalog_index=catalog)
    run = replace(run, scenarios=(ScenarioResult("broad-cards-original", ((observed, verdict),)),))
    report = json.loads(retrieval_reports.write_review_report(run).read_text())
    assert report["turns"][0]["result"] is None
    expected = [r.model_dump(mode="json") if r else None for r in observed.answer_results]
    assert report["turns"][0]["answer_results"] == expected
    assert not report["summary"]["automated_passed"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink semantics")
def test_report_allows_a_declared_workspace_through_a_system_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linked workspace root is valid; links below its private output root are not."""
    from veritycx.service import retrieval_reports

    real = tmp_path / "workspace"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(retrieval_reports, "PROJECT_ROOT", linked)
    monkeypatch.setattr(retrieval_reports, "EVIDENCE_ROOT", linked / "reports")
    assert retrieval_reports.write_review_report(sample_run()).is_file()


@pytest.mark.parametrize(
    "mode,passed,want",
    [("offline", True, 0), ("offline", False, 1), ("live", True, 2), ("live", False, 1)],
)
def test_status_distinguishes_structural_success_from_semantic_acceptance(
    mode: str, passed: bool, want: int
) -> None:
    """A live automated pass remains a non-success until human semantic acceptance."""
    from veritycx.service.retrieval_reports import exit_status, public_summary

    run = sample_run(mode=mode)
    if not passed:
        observed, _ = run.scenarios[0].turns[0]
        turn, _, catalog = overview()
        observed = replace(observed, execution_error="timeout")
        verdict = judge_turn(turn, observed, expected_history=(), catalog_index=catalog)
        run = replace(
            run, scenarios=(ScenarioResult("broad-cards-original", ((observed, verdict),)),)
        )
    assert exit_status(public_summary(run)) == want
