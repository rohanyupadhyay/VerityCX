"""Opt-in acceptance against real models, never replayed rewrite or answer output."""

import json
import os

import pytest

from veritycx.service.retrieval_command import run_regressions
from veritycx.service.retrieval_reports import EVIDENCE_ROOT, PublicSummary

pytestmark = [pytest.mark.live, pytest.mark.support_db]


@pytest.mark.parametrize("repeat", range(3))
def test_original_card_question_gets_cited_product_overview(
    test_database_url: str, repeat: int
) -> None:
    """Fresh real-model turns must answer the original customer request, not clarify it."""
    summary = PublicSummary.model_validate_json(
        json.dumps(
            run_regressions(
                dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url),
                live=True,
                case_ids=["broad-cards-original"],
            )
        )
    )
    turn = summary.scenarios[0].turns[0]
    assert summary.mode == "live" and summary.evidence_kind == "live"
    assert summary.automated_passed, turn.verdict.model_dump_json()
    assert turn.result_kind == "answer"
    assert turn.answer_calls >= 1
    assert set(turn.cited_source_ids) == {"policy-03:0001", "policy-08:0001", "policy-16:0001"}
    report = json.loads((EVIDENCE_ROOT / summary.report_id / "review.json").read_text())
    text = report["turns"][0]["result"]["text"]
    assert all(product in text for product in ("Cedar", "Hazel", "Pine")), text
    assert repeat >= 0


def test_live_discovery_keeps_followup_and_unsupported_boundaries(test_database_url: str) -> None:
    """Broad discovery must not remove genuine ambiguity or invent unsupported product facts."""
    summary = PublicSummary.model_validate_json(
        json.dumps(
            run_regressions(
                dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url),
                live=True,
                case_ids=[
                    "broad-cards-options",
                    "followup-cedar",
                    "followup-missing",
                    "unsupported-product",
                    "unsupported-business",
                ],
            )
        )
    )
    assert summary.mode == "live" and summary.evidence_kind == "live"
    assert summary.automated_passed, json.dumps(
        {
            case.case_id: [turn.verdict.model_dump() for turn in case.turns]
            for case in summary.scenarios
        }
    )
