"""Intercept the actual SDK so rewrite failures cannot hide retries or provider bodies."""

import json

import httpx2
import pytest
from openai import AsyncOpenAI

from veritycx.providers.protocol import ProviderError
from veritycx.providers.rewrite import OpenAIQueryRewriter, RewriteRequest
from veritycx.service.runtime import run_async


def test_rewrite_request_and_sanitized_failure() -> None:
    """The independent stage sends one bounded, tool-free structured request."""
    calls: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["model"] == "rewrite-fixture"
        assert payload["store"] is False
        assert payload["tools"] == []
        assert payload["max_output_tokens"] == 2048
        assert payload["text"]["format"]["strict"] is True
        return httpx2.Response(
            401,
            json={"error": {"message": "secret-rewrite-canary", "type": "invalid_request_error"}},
        )

    async def exercise() -> None:
        async with AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            rewriter = OpenAIQueryRewriter(client, "rewrite-fixture")
            with pytest.raises(ProviderError, match="provider_unavailable") as error:
                await rewriter.rewrite(
                    RewriteRequest(
                        question="Cedar?",
                        context=(),
                        correlation_id="fixture",
                        corpus_version="v2",
                        remaining_seconds=10.0,
                    )
                )
            assert "secret-rewrite-canary" not in str(error.value)

    run_async(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "wire",
    [
        {"disposition": "search", "query": "Cedar card replacement fee"},
        {"disposition": "clarify", "text": "Which card?"},
        {"disposition": "search", "query": ""},
    ],
)
def test_rewrite_real_sdk_parses_success_or_rejects_invalid(wire: dict[str, str]) -> None:
    """Observed SDK metadata stays separate from untrusted structured output."""

    def respond(request: httpx2.Request) -> httpx2.Response:
        """Return a minimal real Responses envelope with authored data."""
        return httpx2.Response(
            200,
            json={
                "id": "resp_fixture",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "sdk-fixture",
                "output": [
                    {
                        "id": "msg_fixture",
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
        """Exercise SDK parsing without an external provider connection."""
        async with AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            rewriter = OpenAIQueryRewriter(client, "rewrite-fixture")
            request = RewriteRequest(
                question="Question?",
                correlation_id="fixture",
                corpus_version="v2",
                remaining_seconds=10.0,
            )
            if wire.get("query") == "":
                with pytest.raises(ProviderError, match="invalid_output"):
                    await rewriter.rewrite(request)
            else:
                result = await rewriter.rewrite(request)
                assert result.result.disposition == wire["disposition"]
                assert result.model == "rewrite-fixture"
                assert result.usage is not None and result.usage.input_tokens == 19

    run_async(exercise())


def test_rewrite_timeout_is_sanitized_without_retry() -> None:
    """A transport timeout is a terminal stage outcome rather than another call."""
    calls = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        """Raise a mock timeout containing a private canary."""
        nonlocal calls
        calls += 1
        raise httpx2.ReadTimeout("private-timeout-canary", request=request)

    async def exercise() -> None:
        """Keep the test offline while using the real SDK timeout conversion."""
        async with AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            with pytest.raises(ProviderError, match="timeout") as error:
                await OpenAIQueryRewriter(client, "fixture").rewrite(
                    RewriteRequest(
                        question="Cedar?",
                        correlation_id="fixture",
                        corpus_version="v2",
                        remaining_seconds=10.0,
                    )
                )
            assert "private-timeout-canary" not in str(error.value)

    run_async(exercise())
