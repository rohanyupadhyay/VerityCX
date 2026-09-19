"""Freeze lexical ranking, Unicode tokenization, deterministic sections and context limits."""

from veritycx.knowledge.index import sections
from veritycx.knowledge.models import KnowledgeDocument
from veritycx.knowledge.retrieval import retrieve, tokens


def test_ranking_and_bounds() -> None:
    """Unique query tokens, deterministic tie ordering and bounded evidence govern selection."""
    assert tokens("\u00c9pargne_ACCOUNT 123") == {"\u00e9pargne", "account", "123"}
    document = KnowledgeDocument(id="fixture", title="Policy", content="Savings policy. " * 500)
    indexed = sections(document, "fixture-v1")
    assert all(len(section.content) <= 2000 for section in indexed)
    assert indexed == sections(document, "fixture-v1")
    assert retrieve("zzzznoevidence", indexed) == []
    result = retrieve("savings savings", indexed)
    assert len(result) <= 6 and sum(len(item.content) for item in result) <= 12000
    assert result == retrieve("savings", indexed)


def test_tie_order_and_recent_context() -> None:
    """Rank ties by source identity and retain a contiguous bounded history suffix."""
    from veritycx.knowledge.retrieval import recent_context
    from veritycx.providers.protocol import ContextMessage

    first = sections(KnowledgeDocument(id="a", title="A", content="alpha beta"), "fixture")[0]
    second = sections(KnowledgeDocument(id="b", title="B", content="alpha gamma"), "fixture")[0]
    assert [item.document_id for item in retrieve("alpha", [second, first])] == ["a", "b"]
    assert retrieve("beta", [second, first]) == [first]
    history = [
        ContextMessage(role="user", text="x" * 8000),
        ContextMessage(role="assistant", text="y" * 8000),
        ContextMessage(role="user", text="z"),
    ]
    assert recent_context(history) == tuple(history[1:])
