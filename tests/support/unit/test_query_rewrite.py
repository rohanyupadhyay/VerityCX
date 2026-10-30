"""Validate the bounded untrusted rewrite contract and explicit offline substitute."""

import pytest
from pydantic import ValidationError

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
        SearchRewrite(disposition="search", query=query)


def test_rewrite_history_bounds() -> None:
    """History is bounded independently of the provider request schema."""
    with pytest.raises(ValidationError):
        RewriteRequest(
            question="Question", context=tuple(ContextMessage(role="user", text="x" * 8000)
                                               for _ in range(3)),
            correlation_id="fixture", corpus_version="v2", remaining_seconds=10.0,
        )


def test_offline_standalone_and_followup() -> None:
    """Authored cases prove stage routing only, not live model fidelity."""
    async def exercise() -> None:
        rewriter = DeterministicQueryRewriter()
        request = RewriteRequest(
            question="What is its replacement fee?",
            context=(ContextMessage(role="user", text="Tell me about the Cedar card."),),
            correlation_id="fixture", corpus_version="v2", remaining_seconds=10.0,
        )
        result = await rewriter.rewrite(request)
        assert isinstance(result.result, SearchRewrite)
        assert result.result.query == "What is the Cedar card replacement fee?"
        assert result.usage is None
        ambiguous = request.model_copy(update={"context": (
            ContextMessage(role="user", text="Compare Cedar and Hazel cards."),
        )})
        assert (await rewriter.rewrite(ambiguous)).result.disposition == "clarify"
        assert (await rewriter.rewrite(request.model_copy(update={"context": ()}))).result.disposition == "clarify"
        standalone = request.model_copy(update={"question": "Cedar card fee", "context": ()})
        assert (await rewriter.rewrite(standalone)).result == SearchRewrite(
            disposition="search", query="Cedar card fee"
        )
    run_async(exercise())
