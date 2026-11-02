"""Keep overview scope honest without weakening source or publication bounds."""

import json

import httpx2
import pytest
from openai import AsyncOpenAI

from veritycx.knowledge.index import sections
from veritycx.knowledge.models import KnowledgeDocument
from veritycx.knowledge.scope import (
    OVERVIEW_SCOPE_NOTE,
    CategoryCoverage,
    SearchContext,
    SearchScope,
)
from veritycx.policy.outputs import validate_result
from veritycx.providers.openai import OpenAIProvider
from veritycx.providers.protocol import Claim, ProviderError, ProviderRequest, ProviderResult
from veritycx.service.runtime import run_async


def request(*, overview: bool = True) -> ProviderRequest:
    """Supply one authored policy with a measured discovery context."""
    evidence = sections(
        KnowledgeDocument(
            id="cedar",
            title="Cedar card",
            content="The fictional Cedar card replacement fee is 7 synthetic dollars.",
        ),
        "fixture-v3",
    )
    return ProviderRequest(
        correlation_id="fixture",
        question="What cards are documented?",
        evidence=tuple(evidence),
        remaining_seconds=60.0,
        search_context=SearchContext(
            search_scope=SearchScope(
                scope="category_overview" if overview else "focused",
                categories=("cards",) if overview else (),
            ),
            coverage=CategoryCoverage(
                eligible_document_count=1, represented_document_count=1, coverage_truncated=False
            )
            if overview
            else None,
        ),
    )


def answer(*texts: str) -> ProviderResult:
    """Return cited authored claims; publication validates the actual joined text."""
    return ProviderResult(
        disposition="answer",
        model="fixture",
        claims=tuple(Claim(text=text, evidence_ids=("cedar:0001",)) for text in texts),
    )


def test_overview_scope_note_and_citations() -> None:
    """Scope wording is application-owned and does not replace source attribution."""
    result = validate_result(request(), answer("Cedar is documented."))
    assert result.text == "Cedar is documented.\n" + OVERVIEW_SCOPE_NOTE
    assert result.text.count(OVERVIEW_SCOPE_NOTE) == 1
    assert result.citations[0].document_id == "cedar"
    assert request().prompt_version == 3


def test_exact_publication_limit_includes_scope_note_and_separators() -> None:
    """The note and both kinds of separator fit the unchanged 8000-character cap."""
    value = request()
    limit = value.answer_text_limit
    assert limit == 8000 - len(OVERVIEW_SCOPE_NOTE) - 1
    assert len(validate_result(value, answer("x" * limit)).text) == 8000
    joined = validate_result(value, answer("x" * 2000, "y" * (limit - 2001)))
    assert len(joined.text) == 8000
    with pytest.raises(ProviderError, match="invalid_output"):
        validate_result(value, answer("x" * (limit + 1)))
    with pytest.raises(ProviderError, match="invalid_output"):
        validate_result(value, answer("x" * 2000, "y" * (limit - 2000)))


def test_focused_answers_do_not_get_discovery_scope_note() -> None:
    """Normal answers keep their original publication budget and wording."""
    value = request(overview=False)
    assert value.answer_text_limit == 8000
    assert validate_result(value, answer("A documented fee.")).text == "A documented fee."


@pytest.mark.parametrize("kind", ["abstain", "clarify"])
def test_nonanswers_do_not_get_product_list_note(kind: str) -> None:
    """A clarification or abstention must not imply a successful product overview."""
    value = ProviderResult.model_validate_json(
        json.dumps(
            {"disposition": kind, "text": "The qualifier is not supported.", "model": "fixture"}
        )
    )
    assert validate_result(request(), value).text == "The qualifier is not supported."


def test_overview_cannot_authorize_a_foreign_citation() -> None:
    """Category scope never creates permission to cite unselected policy evidence."""
    value = ProviderResult(
        disposition="answer",
        model="fixture",
        claims=(Claim(text="Invented", evidence_ids=("foreign:0001",)),),
    )
    with pytest.raises(ProviderError, match="invalid_output"):
        validate_result(request(), value)


@pytest.mark.parametrize(
    "question",
    [
        "What cards are eligible for businesses?",
        "What are the Martian asteroid vault products?",
    ],
)
def test_real_provider_keeps_original_qualifiers_with_overview_metadata(question: str) -> None:
    """A mistaken category classifier cannot replace the original customer request."""
    calls = 0
    value = request().model_copy(update={"question": question})

    def respond(wire: httpx2.Request) -> httpx2.Response:
        """Inspect the actual SDK payload without making an external request."""
        nonlocal calls
        calls += 1
        payload = json.loads(wire.content)
        body = json.loads(payload["input"])
        assert body["question"] == question and body["prompt_version"] == 3
        assert body["search_context"]["search_scope"]["categories"] == ["cards"]
        assert "qualifiers" in payload["instructions"]
        assert "not policy evidence" in payload["instructions"]
        assert str(value.answer_text_limit) in payload["instructions"]
        assert payload["tools"] == [] and payload["store"] is False
        return httpx2.Response(401, json={"error": {"message": "fixture", "type": "fixture"}})

    async def exercise() -> None:
        """Run one nonretrying mocked Responses request."""
        async with AsyncOpenAI(
            api_key="offline-test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        ) as client:
            with pytest.raises(ProviderError, match="provider_unavailable"):
                await OpenAIProvider(client).generate(value)

    run_async(exercise())
    assert calls == 1
