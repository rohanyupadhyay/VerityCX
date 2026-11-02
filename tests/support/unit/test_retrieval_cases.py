"""Protect the authored regression inventory and reject unsafe or ambiguous inputs."""

import json
from collections import Counter
from pathlib import Path

import pytest

from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import build_manifest
from veritycx.providers.deterministic import fixture_cases


def test_catalog_covers_the_agreed_scenarios_and_sources() -> None:
    """Dropping a family, a conversation turn or required support breaks the inventory."""
    from veritycx.service.retrieval_cases import load_cases, validate_case_sources

    cases = load_cases()
    assert len(cases.scenarios) == 24
    assert sum(len(case.turns) for case in cases.scenarios) == 31
    assert Counter(case.family for case in cases.scenarios) == {
        "plurals": 4,
        "paraphrases": 6,
        "broad": 5,
        "followups": 5,
        "unsupported": 4,
    }
    root, _, pin = source_mode("synthetic", validation=True)
    manifest = build_manifest(root, "synthetic", pin)
    validate_case_sources(cases, manifest)
    original = next(case for case in cases.scenarios if case.id == "broad-cards-original")
    assert original.turns[0].question == "What cards does VerityCX offers?"
    assert set(original.turns[0].expected.evidence.required_documents) == {
        "policy-03",
        "policy-08",
        "policy-16",
    }
    assert len(fixture_cases()) == 40


def test_selection_is_bounded_unique_and_in_catalog_order() -> None:
    """Duplicate selections cannot multiply live calls, and unknown IDs cannot run."""
    from veritycx.service.retrieval_cases import load_cases, select_cases

    cases = load_cases()
    assert [
        case.id for case in select_cases(cases, ["broad-cards-original", "plural-cedar-card"])
    ] == ["plural-cedar-card", "broad-cards-original"]
    for selected in (["unknown"], ["plural-cedar-card"] * 2, []):
        with pytest.raises(ValueError):
            select_cases(cases, selected)


@pytest.mark.parametrize("mutation", ["extra", "alias", "category", "turn", "case", "bound"])
def test_catalog_rejects_ambiguous_or_unbounded_entries(mutation: str) -> None:
    """Malformed scenario declarations fail before storage or providers are used."""
    from veritycx.service.retrieval_cases import RegressionSet, load_cases

    value = json.loads(load_cases().model_dump_json())
    scenario = value["scenarios"][0]
    turn = scenario["turns"][0]
    if mutation == "extra":
        turn["surprise"] = "forbidden"
    elif mutation == "alias":
        turn["conversation"] = "undeclared"
    elif mutation == "category":
        turn["expected"]["scopes"] = [{"scope": "category_overview", "categories": ["unknown"]}]
    elif mutation == "turn":
        scenario["turns"].append(turn)
    elif mutation == "case":
        value["scenarios"][1]["id"] = scenario["id"]
    else:
        value["scenarios"] *= 2
    with pytest.raises(ValueError):
        RegressionSet.model_validate_json(json.dumps(value))


def test_loader_rejects_duplicate_json_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duplicate JSON keys cannot quietly replace an authored expectation."""
    from veritycx.service import retrieval_cases

    path = tmp_path / "cases.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    monkeypatch.setattr(retrieval_cases, "CASES_PATH", path)
    with pytest.raises(ValueError):
        retrieval_cases.load_cases()


def test_source_validation_rejects_nonexistent_policy() -> None:
    """A typo in an expected policy ID cannot become a meaningless passing test."""
    from veritycx.service.retrieval_cases import RegressionSet, load_cases, validate_case_sources

    value = json.loads(load_cases().model_dump_json())
    value["scenarios"][0]["turns"][0]["expected"]["evidence"]["required_documents"] = ["foreign"]
    cases = RegressionSet.model_validate_json(json.dumps(value))
    root, _, pin = source_mode("synthetic", validation=True)
    with pytest.raises(ValueError):
        validate_case_sources(cases, build_manifest(root, "synthetic", pin))


def test_replays_are_complete_and_separate_from_expectations() -> None:
    """A missing replay or an answer on a clarification branch is rejected."""
    from veritycx.service.retrieval_cases import load_cases, load_replays

    cases = load_cases()
    root, _, pin = source_mode("synthetic", validation=True)
    replays = load_replays(cases, build_manifest(root, "synthetic", pin))
    assert len(replays) == 31
    assert set(replays) == {(case.id, turn.id) for case in cases.scenarios for turn in case.turns}
    missing = replays[("followup-missing", "t1")]
    assert missing.rewrite.result.disposition == "clarify" and missing.answer is None
    assert replays[("unsupported-absent", "t1")].answer is None


def test_replay_loader_rejects_missing_and_extra_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay key mismatches fail before a provider can return the wrong turn's result."""
    from veritycx.service import retrieval_cases

    original = json.loads(retrieval_cases.REPLAYS_PATH.read_bytes())
    path = tmp_path / "replays.json"
    monkeypatch.setattr(retrieval_cases, "REPLAYS_PATH", path)
    root, _, pin = source_mode("synthetic", validation=True)
    manifest = build_manifest(root, "synthetic", pin)
    for turns in (original["turns"][:-1], original["turns"] + [original["turns"][0]]):
        path.write_text(json.dumps({**original, "turns": turns}), encoding="utf-8")
        with pytest.raises(ValueError):
            retrieval_cases.load_replays(retrieval_cases.load_cases(), manifest)
