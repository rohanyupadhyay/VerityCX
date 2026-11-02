"""Exercise the live adapters and real pipeline using only intercepted SDK transports."""

import json
from pathlib import Path

import httpx2
import pytest
from openai import AsyncOpenAI

from veritycx.knowledge.configuration import active_corpus
from veritycx.persistence.database import database_pool
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_live_path_never_sends_gold_and_uses_observed_history(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual SDK sees questions/history/evidence, never expected answers or replays."""
    from veritycx.service import retrieval_cases
    from veritycx.service.retrieval_providers import live_provider_factory
    from veritycx.service.retrieval_runner import exercise_regressions

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("live replay access")

    monkeypatch.setattr(retrieval_cases, "load_replays", forbidden)
    requests: list[dict[str, object]] = []
    observed_history = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        assert "GOLD_EXPECTATION_CANARY" not in json.dumps(payload)
        assert "required_facts" not in json.dumps(
            payload
        ) and "scripted-answer-v1" not in json.dumps(payload)
        assert payload["store"] is False and payload["tools"] == []
        body = json.loads(payload["input"])
        requests.append(body)
        wire: dict[str, object]
        if "available_categories" in body:
            observed_history.append(body["context"])
            wire = {
                "disposition": "search",
                "query": "What is the Cedar card replacement fee?",
                "scope": "focused",
                "categories": [],
            }
        else:
            wire = {
                "disposition": "answer",
                "claims": [
                    {
                        "text": "Transport: Cedar replacement costs 7 synthetic dollars.",
                        "evidence_ids": ["policy-03:0001"],
                    }
                ],
            }
        return httpx2.Response(
            200,
            json={
                "id": "resp_offline",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": payload["model"],
                "output": [
                    {
                        "id": "msg_offline",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"result": wire}),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 19,
                    "output_tokens": 7,
                    "total_tokens": 26,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    async def exercise() -> None:
        manifest, evidence = active_corpus("synthetic")
        case = retrieval_cases.select_cases(retrieval_cases.load_cases(), ["followup-cedar"])[0]
        case = case.model_copy(
            update={
                "turns": tuple(
                    t.model_copy(
                        update={
                            "expected": t.expected.model_copy(
                                update={"required_facts": ("GOLD_EXPECTATION_CANARY",)}
                            )
                        }
                    )
                    for t in case.turns
                )
            }
        )
        async with (
            AsyncOpenAI(
                api_key="offline-test",
                max_retries=0,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            ) as client,
            database_pool(test_database_url) as pool,
        ):
            result = await exercise_regressions(
                pool,
                Settings(),
                [case],
                manifest=manifest,
                evidence=evidence,
                providers=live_provider_factory(client, Settings()),
                mode="live",
            )
        assert result.passed
        assert len(requests) == 4
        assert observed_history[0] == []
        assert observed_history[1] == [
            {"role": "user", "text": "What is the Cedar card replacement fee?"},
            {
                "role": "assistant",
                "text": "Transport: Cedar replacement costs 7 synthetic dollars.",
            },
        ]

    run_async(exercise())


def test_live_provider_failure_is_an_execution_failure(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The actual child live branch uses the SDK and never substitutes replay output."""
    import veritycx.service.retrieval_command as retrieval_command
    import veritycx.service.retrieval_reports as retrieval_reports
    from veritycx.service.retrieval_reports import exit_status

    calls: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        """Return a real SDK rate-limit envelope without any network access."""
        calls.append(request)
        return httpx2.Response(
            429, json={"error": {"message": "PRIVATE_API_ERROR_CANARY", "type": "rate_limit"}}
        )

    def client_factory(**kwargs: object) -> AsyncOpenAI:
        """Intercept only the child's external SDK transport."""
        assert kwargs == {"api_key": "offline-test", "max_retries": 0}
        return AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    def forbidden(*args: object, **kwargs: object) -> None:
        """Loading replay outputs in the live child is a contract violation."""
        raise AssertionError("live replay access")

    monkeypatch.setattr(retrieval_reports, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(retrieval_reports, "EVIDENCE_ROOT", tmp_path / "mock-sdk-reports")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test")
    monkeypatch.setattr(retrieval_command, "AsyncOpenAI", client_factory)
    monkeypatch.setattr(retrieval_command, "load_replays", forbidden)

    async def exercise() -> None:
        """Run the child orchestration itself, including actual database and reporting."""
        summary = await retrieval_command._exercise_child(
            live=True, case_ids=["unsupported-product"]
        )
        assert summary["automated_passed"] is False and len(calls) == 1
        assert exit_status(summary) == 1
        assert "PRIVATE_API_ERROR_CANARY" not in json.dumps(summary)

    run_async(exercise())
