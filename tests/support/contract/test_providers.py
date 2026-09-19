"""Enforce bounded structured provider output and selected-evidence citation membership."""

import pytest

from veritycx.knowledge.models import EvidenceSection
from veritycx.policy.outputs import validate_result
from veritycx.providers.protocol import Claim, ProviderError, ProviderRequest, ProviderResult


def test_selected_citations() -> None:
    """A real source identifier outside the supplied evidence must still be rejected."""
    evidence = EvidenceSection(
        corpus_version="fixture",
        document_id="policy",
        section_id="policy:0001",
        section_hash="a" * 64,
        title="Policy",
        content="Synthetic savings",
    )
    request = ProviderRequest(
        correlation_id="opaque", question="Savings?", evidence=(evidence,), remaining_seconds=30.0
    )
    answer = ProviderResult(
        disposition="answer",
        claims=(Claim(text="Synthetic savings", evidence_ids=("policy:0001",)),),
        model="fixture",
    )
    assert validate_result(request, answer).citations[0].document_id == "policy"
    forged = ProviderResult(
        disposition="answer",
        claims=(Claim(text="Forged", evidence_ids=("foreign:0001",)),),
        model="fixture",
    )
    with pytest.raises(ProviderError, match="invalid_output"):
        validate_result(request, forged)


def test_sdk_request_has_no_hidden_retry() -> None:
    """Intercept the real SDK transport and prove a rate limit sends only one request."""
    import json

    import httpx2
    from openai import AsyncOpenAI

    from veritycx.providers.openai import OpenAIProvider
    from veritycx.service.runtime import run_async

    calls: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        """Capture only synthetic test payloads and return an offline error response."""
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["tools"] == []
        assert payload["max_output_tokens"] == 2048
        assert payload["text"]["format"]["strict"] is True
        return httpx2.Response(
            429, json={"error": {"message": "secret-canary", "type": "rate_limit"}}
        )

    async def exercise() -> None:
        """Call only the mock transport with a noncredential placeholder."""
        async with AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            provider = OpenAIProvider(client)
            request = ProviderRequest(
                correlation_id="opaque", question="Fixture?", evidence=(), remaining_seconds=2.0
            )
            with pytest.raises(ProviderError, match="provider_unavailable") as error:
                await provider.generate(request)
            assert "secret-canary" not in str(error.value)

    run_async(exercise())
    assert len(calls) == 1


def test_all_frozen_deterministic_cases() -> None:
    """All forty cases remain finite synthetic responses, separate from live review."""
    from veritycx.knowledge.configuration import source_mode
    from veritycx.knowledge.manifest import build_manifest, load_sections
    from veritycx.knowledge.retrieval import retrieve
    from veritycx.providers.deterministic import DeterministicProvider, fixture_cases
    from veritycx.service.runtime import run_async

    root, _, pin = source_mode("synthetic")
    corpus = load_sections(root, build_manifest(root, "synthetic", pin))

    async def exercise() -> None:
        """Use no provider credentials and validate every selected citation."""
        for case in fixture_cases():
            request = ProviderRequest(
                correlation_id=case.id,
                question=case.question,
                evidence=tuple(retrieve(case.question, corpus)),
                remaining_seconds=60.0,
            )
            result = await DeterministicProvider().generate(request)
            assert validate_result(request, result).kind == case.disposition
            assert result.usage is None

    run_async(exercise())


@pytest.mark.parametrize(
    "payload",
    [
        {"disposition": "answer", "claims": [], "model": "fixture"},
        {"disposition": "abstain", "text": "No evidence", "model": "fixture", "tool": "transfer"},
        {"disposition": "abstain", "text": "x" * 8001, "model": "fixture"},
    ],
)
def test_malformed_provider_output(payload: dict[str, object]) -> None:
    """Reject capability fields, empty unsupported answers and oversized output."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProviderResult.model_validate(payload)
