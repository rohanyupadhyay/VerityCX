"""Validate the bounded untrusted rewrite contract and explicit offline substitute."""

import json

import pytest
from pydantic import ValidationError

from veritycx.knowledge.scope import CategoryHint, SearchScope
from veritycx.providers.protocol import ContextMessage
from veritycx.providers.rewrite import (
    DeterministicQueryRewriter,
    RewriteRequest,
    SearchRewrite,
)
from veritycx.service.runtime import run_async


@pytest.mark.parametrize("query", ["", " ", "x" * 8001])
def test_invalid_rewrite_query(query: str) -> None:
    """Empty and oversized rewritten text cannot enter retrieval."""
    with pytest.raises(ValidationError):
        SearchRewrite(disposition="search", query=query, scope="focused", categories=())


def test_rewrite_history_bounds() -> None:
    """History is bounded independently of the provider request schema."""
    with pytest.raises(ValidationError):
        RewriteRequest(
            question="Question",
            context=tuple(ContextMessage(role="user", text="x" * 8000) for _ in range(3)),
            correlation_id="fixture",
            corpus_version="v2",
            remaining_seconds=10.0,
        )


def test_offline_standalone_and_followup() -> None:
    """Authored cases prove stage routing only, not live model fidelity."""

    async def exercise() -> None:
        rewriter = DeterministicQueryRewriter()
        request = RewriteRequest(
            question="What is its replacement fee?",
            context=(ContextMessage(role="user", text="Tell me about the Cedar card."),),
            correlation_id="fixture",
            corpus_version="v2",
            remaining_seconds=10.0,
        )
        result = await rewriter.rewrite(request)
        assert isinstance(result.result, SearchRewrite)
        assert result.result.query == "What is the Cedar card replacement fee?"
        assert result.usage is None
        ambiguous = request.model_copy(
            update={
                "context": (ContextMessage(role="user", text="Compare Cedar and Hazel cards."),)
            }
        )
        assert (await rewriter.rewrite(ambiguous)).result.disposition == "clarify"
        assert (
            await rewriter.rewrite(request.model_copy(update={"context": ()}))
        ).result.disposition == "clarify"
        standalone = request.model_copy(update={"question": "Cedar card fee", "context": ()})
        assert (await rewriter.rewrite(standalone)).result == SearchRewrite(
            disposition="search", query="Cedar card fee", scope="focused", categories=()
        )

    run_async(exercise())


@pytest.mark.parametrize(
    "payload",
    [
        {"disposition": "search", "query": "cards"},
        {"disposition": "search", "query": "cards", "scope": "focused"},
        {"disposition": "search", "query": "cards", "scope": "category_overview", "categories": []},
        {"disposition": "search", "query": "cards", "scope": "focused", "categories": ["cards"]},
        {
            "disposition": "search",
            "query": "cards",
            "scope": "category_overview",
            "categories": ["cards", "cards"],
        },
        {
            "disposition": "search",
            "query": "cards",
            "scope": "category_overview",
            "categories": ["unknown"],
        },
    ],
)
def test_rewrite_requires_complete_consistent_scope(payload: dict[str, object]) -> None:
    """Old or inconsistent model output must not silently gain search scope."""
    with pytest.raises(ValidationError):
        SearchRewrite.model_validate_json(json.dumps(payload))


def test_rewrite_canonical_scope_and_request_hints() -> None:
    """Canonical scope and trusted availability hints participate in request identity."""
    result = SearchRewrite(
        disposition="search",
        query="banking options",
        scope="category_overview",
        categories=("cards", "accounts"),
    )
    assert result.search_scope() == SearchScope(
        scope="category_overview", categories=("accounts", "cards")
    )
    request = RewriteRequest(
        question="Cards?",
        correlation_id="fixture",
        corpus_version="v3",
        remaining_seconds=10.0,
        available_categories=(CategoryHint(key="cards", label="Cards"),),
    )
    assert request.prompt_version == 2
    assert "available_categories" in request.model_dump_json()
    for hints in (
        (CategoryHint(key="cards", label="Cards"),) * 7,
        (CategoryHint(key="cards", label="Cards"),) * 2,
    ):
        with pytest.raises(ValidationError):
            RewriteRequest(
                question="Cards?",
                correlation_id="fixture",
                corpus_version="v3",
                remaining_seconds=10.0,
                available_categories=hints,
            )


@pytest.mark.parametrize(
    "question,categories",
    [
        ("What cards does VerityCX offers?", ("cards",)),
        ("What are my card options?", ("cards",)),
        ("Show accounts and cards", ("accounts", "cards")),
        ("What is the Cedar replacement fee?", ()),
        ("Which cards are eligible for businesses?", ()),
        ("What is the fee for a Martian asteroid vault?", ()),
    ],
)
def test_offline_scopes_are_explicit_authored_cases(
    question: str, categories: tuple[str, ...]
) -> None:
    """Authored cases test control flow without inventing a local production classifier."""

    async def exercise() -> None:
        result = await DeterministicQueryRewriter().rewrite(
            RewriteRequest(
                question=question,
                correlation_id="fixture",
                corpus_version="v3",
                remaining_seconds=10.0,
            )
        )
        assert isinstance(result.result, SearchRewrite)
        assert result.result.categories == categories
        assert result.result.query == question

    run_async(exercise())
