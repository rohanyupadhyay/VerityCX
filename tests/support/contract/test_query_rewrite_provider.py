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
            401, json={"error": {"message": "secret-rewrite-canary", "type": "invalid_request_error"}}
        )

    async def exercise() -> None:
        async with AsyncOpenAI(
            api_key="offline-test", max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            rewriter = OpenAIQueryRewriter(client, "rewrite-fixture")
            with pytest.raises(ProviderError, match="provider_unavailable") as error:
                await rewriter.rewrite(RewriteRequest(
                    question="Cedar?", context=(), correlation_id="fixture",
                    corpus_version="v2", remaining_seconds=10.0,
                ))
            assert "secret-rewrite-canary" not in str(error.value)
    run_async(exercise())
    assert len(calls) == 1
