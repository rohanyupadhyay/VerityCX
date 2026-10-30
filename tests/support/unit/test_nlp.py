"""Test real English normalization and lexical retrieval against approved fixture text."""

import pytest

from veritycx.knowledge.index import sections
from veritycx.knowledge.models import KnowledgeDocument
from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.retrieval import select_evidence


class CountingExpander:
    """Record fallback use without depending on lexical resource senses."""

    def __init__(self) -> None:
        """Start with no fallback use."""
        self.calls = 0

    def expand(self, tokens: object, *, vocabulary: frozenset[str]) -> tuple[str, ...]:
        """Return a fixed supported alternative only when requested."""
        self.calls += 1
        return ("fee",) if "fee" in vocabulary else ()


def test_plural_forms_match() -> None:
    """Noun inflections normalize symmetrically."""
    normalizer = TextNormalizer()
    assert normalizer.terms("cards fees replacements") == normalizer.terms("card fee replacement")


def test_product_names_and_numbers_preserved() -> None:
    """Product and numeric constraints retain original text without lexical expansion."""
    values = TextNormalizer().analyze("Cedar card fee is not more than 7 dollars")
    assert any(token.surface == "Cedar" and token.protected for token in values)
    assert any(token.surface == "7" and token.protected for token in values)
    assert any(token.lemma == "not" and token.constraint for token in values)


def test_cards_question_ignores_does_and_matches_card() -> None:
    """The original wording finds cards rather than unrelated auxiliary-word hits."""
    from veritycx.knowledge.configuration import source_mode
    from veritycx.knowledge.manifest import build_manifest, load_sections

    root, _, pin = source_mode("synthetic")
    evidence = load_sections(root, build_manifest(root, "synthetic", pin))
    expander = CountingExpander()
    question = "What cards does VerityCX offers?"
    result = select_evidence(
        question, question, evidence, normalizer=TextNormalizer(), expander=expander
    )
    assert {"policy-03", "policy-08"} <= {item.document_id for item in result.sections}
    assert not any(item.document_id.startswith("conflict-") for item in result.sections)
    assert expander.calls == 0


def test_title_only_match_and_synonyms_only_after_empty_primary() -> None:
    """Titles participate, and a successful primary pass prevents expansion."""
    evidence = sections(KnowledgeDocument(id="a", title="Card fee", content="Seven dollars."), "v2")
    normalizer = TextNormalizer()
    expander = CountingExpander()
    primary = select_evidence("cards", "card", evidence, normalizer=normalizer, expander=expander)
    assert primary.sections == tuple(evidence)
    assert primary.mode == "primary" and expander.calls == 0
    fallback = select_evidence(
        "tariff", "tariff", evidence, normalizer=normalizer, expander=expander
    )
    assert fallback.sections == tuple(evidence)
    assert fallback.mode == "synonym" and expander.calls == 1


def test_common_words_or_constraints_alone_select_nothing() -> None:
    """Negation is preserved without becoming the sole reason to retrieve a passage."""
    evidence = sections(
        KnowledgeDocument(id="a", title="Policy", content="This does not apply."), "v2"
    )
    result = select_evidence(
        "what does not",
        "what does not",
        evidence,
        normalizer=TextNormalizer(),
        expander=CountingExpander(),
    )
    assert result.sections == ()


def test_retrieval_bounds_and_ties() -> None:
    """Duplicate concepts and shuffled input retain stable bounded selection."""
    evidence = [
        section
        for number in reversed(range(8))
        for section in sections(
            KnowledgeDocument(id=str(number), title="Card fee", content="card fee " * 210), "v2"
        )
    ]
    normalizer = TextNormalizer()
    expander = CountingExpander()
    first = select_evidence("card", "card", evidence, normalizer=normalizer, expander=expander)
    second = select_evidence(
        "cards cards", "card", evidence, normalizer=normalizer, expander=expander
    )
    assert first == second
    assert len(first.sections) <= 6
    assert sum(len(section.content) for section in first.sections) <= 12000
    assert [section.document_id for section in first.sections] == sorted(
        section.document_id for section in first.sections
    )


def test_only_passages_are_cached_and_changed_text_is_reprocessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated approved evidence avoids inference; user queries remain uncached."""
    from collections.abc import Iterable
    from typing import cast

    from spacy.language import Language
    from spacy.tokens import Doc

    normalizer = TextNormalizer()
    actual = normalizer.pipeline
    passage_calls: list[str] = []
    query_calls: list[str] = []

    class SpyPipeline:
        """Observe inference calls while retaining the actual model's annotations."""

        def __call__(self, text: str) -> Doc:
            """Record a query that must never enter the passage cache."""
            query_calls.append(text)
            return actual(text)

        def pipe(self, texts: Iterable[str], *, batch_size: int) -> Iterable[Doc]:
            """Record only the passage texts sent for model inference."""
            values = list(texts)
            passage_calls.extend(values)
            return actual.pipe(values, batch_size=batch_size)

    monkeypatch.setattr(normalizer, "pipeline", cast(Language, SpyPipeline()))
    assert normalizer.terms_many(["Cedar card fee"]) == normalizer.terms_many(["Cedar card fee"])
    assert passage_calls == ["Cedar card fee"]
    normalizer.terms_many(["Cedar card replacement"])
    assert passage_calls == ["Cedar card fee", "Cedar card replacement"]
    normalizer.terms("customer question")
    normalizer.terms("customer question")
    assert query_calls == ["customer question", "customer question"]


def test_passage_cache_eviction_preserves_large_batch_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch larger than the cache must not evict inputs needed later in that batch."""
    from collections.abc import Iterable
    from typing import cast

    from spacy.language import Language
    from spacy.tokens import Doc

    normalizer = TextNormalizer()
    actual = normalizer.pipeline

    class TokenOnlyPipeline:
        """Keep the eviction test cheap and independent of model inference."""

        def pipe(self, texts: Iterable[str], *, batch_size: int) -> Iterable[Doc]:
            """Tokenize synthetic passages without running trained components."""
            return (actual.make_doc(text) for text in texts)

    monkeypatch.setattr(normalizer, "pipeline", cast(Language, TokenOnlyPipeline()))
    texts = [f"passage{number}" for number in range(4096)]
    normalizer.terms_many(texts)
    assert len(normalizer.terms_many(["newpassage", *texts])) == 4097
