"""Verify bounded source coverage without changing focused lexical selection."""

from collections.abc import Sequence

import pytest

from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.category_retrieval import select_scoped_evidence
from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.index import sections
from veritycx.knowledge.manifest import build_manifest, load_sections
from veritycx.knowledge.models import CatalogEntry, EvidenceSection, KnowledgeDocument
from veritycx.knowledge.nlp import SearchToken, TextNormalizer
from veritycx.knowledge.retrieval import RetrievalSelection, select_evidence
from veritycx.knowledge.scope import SearchScope
from veritycx.policy.sources import SourceError


class CountingExpander:
    """Observe exactly when a search invokes the existing synonym policy."""

    def __init__(self) -> None:
        """Start with no expansions."""
        self.calls = 0

    def expand(
        self, tokens: Sequence[SearchToken], *, vocabulary: frozenset[str]
    ) -> tuple[str, ...]:
        """Return an authored fallback without downloading or consulting a model."""
        self.calls += 1
        return ("fee",)


def select(
    evidence: list[EvidenceSection],
    catalog: Sequence[CatalogEntry],
    *,
    query: str = "cards",
    categories: tuple[CategoryKey, ...] = ("cards",),
    expander: CountingExpander | None = None,
) -> RetrievalSelection:
    """Run category selection with the real pinned English normalizer."""
    return select_scoped_evidence(
        query,
        query,
        evidence,
        search_scope=SearchScope(
            scope="category_overview",
            categories=categories,
        ),
        catalog_index=catalog,
        normalizer=TextNormalizer(),
        expander=expander or CountingExpander(),
    )


def document(
    identifier: str,
    title: str,
    category: CategoryKey,
    *,
    long: bool = False,
) -> tuple[list[EvidenceSection], CatalogEntry]:
    """Build independent authored documents with optionally many passages."""
    item = KnowledgeDocument(
        id=identifier, title=title, content="Approved policy details. " * (500 if long else 1)
    )
    return sections(item, "fixture-v3"), CatalogEntry(
        document_id=identifier,
        title=title,
        category=category,
    )


def test_original_cards_overview_covers_pine() -> None:
    """Pine is selected through approved membership even without a card token."""
    root, _, pin = source_mode("synthetic")
    manifest = build_manifest(root, "synthetic", pin)
    assert manifest.catalog_index is not None
    expander = CountingExpander()
    result = select(
        load_sections(root, manifest),
        manifest.catalog_index,
        query="What cards does VerityCX offers?",
        expander=expander,
    )
    assert {item.document_id for item in result.sections} == {"policy-03", "policy-08", "policy-16"}
    assert result.mode == "category" and result.expanded_term_count == 0
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.eligible_document_count == 3
    assert result.context.coverage.represented_document_count == 3
    assert not result.context.coverage.coverage_truncated and expander.calls == 0


@pytest.mark.parametrize("query", ["Cedar fee", "zzzxunknown"])
def test_focused_equals_v2(query: str) -> None:
    """Focused selection preserves the original ranking, IDs, bounds and fallback calls."""
    evidence = sections(
        KnowledgeDocument(id="cedar", title="Cedar fee", content="The card fee is documented."),
        "v3",
    )
    normalizer = TextNormalizer()
    baseline_expander, wrapper_expander = CountingExpander(), CountingExpander()
    baseline = select_evidence(
        query, query, evidence, normalizer=normalizer, expander=baseline_expander
    )
    wrapped = select_scoped_evidence(
        query,
        query,
        evidence,
        search_scope=SearchScope(scope="focused", categories=()),
        catalog_index=(CatalogEntry(document_id="cedar", title="Cedar fee", category="cards"),),
        normalizer=normalizer,
        expander=wrapper_expander,
    )
    assert wrapped.sections == baseline.sections
    assert wrapped.mode == baseline.mode
    assert wrapped.expanded_term_count == baseline.expanded_term_count
    assert wrapper_expander.calls == baseline_expander.calls
    assert wrapped.context is not None and wrapped.context.coverage is None


def test_empty_category_stays_empty_without_global_fallback() -> None:
    """Missing approved category documents cannot authorize a wider search."""
    evidence, entry = document("account", "Card fee mentioned in an account policy", "accounts")
    expander = CountingExpander()
    result = select(evidence, (entry,), expander=expander)
    assert result.sections == () and result.mode == "empty"
    assert expander.calls == 0
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.eligible_document_count == 0
    assert not result.context.coverage.coverage_truncated


def test_large_multicategory_overview_is_fair_bounded_and_stable() -> None:
    """Cover six different documents before spending slots on duplicate passages."""
    evidence: list[EvidenceSection] = []
    catalog: list[CatalogEntry] = []
    for category in ("accounts", "cards"):
        for number in range(5):
            parts, entry = document(
                f"{category}-{number}", f"{category} {number}", category, long=True
            )
            evidence.extend(parts)
            catalog.append(entry)
    result = select(evidence, catalog, categories=("cards", "accounts"))
    assert len(result.sections) == 6
    identifiers = {item.document_id for item in result.sections}
    assert len(identifiers) == 6
    assert sum(name.startswith("accounts") for name in identifiers) == 3
    assert sum(name.startswith("cards") for name in identifiers) == 3
    assert sum(len(item.content) for item in result.sections) <= 12000
    assert result == select(
        list(reversed(evidence)), tuple(reversed(catalog)), categories=("accounts", "cards")
    )
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.represented_document_count == 6
    assert result.context.coverage.eligible_document_count == 10
    assert result.context.coverage.coverage_truncated
    assert all(item in evidence for item in result.sections)


def test_spare_slots_add_context_only_after_document_coverage() -> None:
    """Long documents get spare sections after all eligible documents are represented."""
    evidence: list[EvidenceSection] = []
    catalog: list[CatalogEntry] = []
    for number in range(3):
        parts, entry = document(str(number), f"Card {number}", "cards", long=True)
        evidence.extend(parts)
        catalog.append(entry)
    result = select(evidence, catalog)
    assert len(result.sections) == 6
    assert len({item.document_id for item in result.sections}) == 3
    assert result.context is not None and result.context.coverage is not None
    assert not result.context.coverage.coverage_truncated


def test_related_versions_are_indivisible_at_budget_boundary() -> None:
    """A related pair cannot be reduced to one apparent policy truth in the last slot."""
    evidence: list[EvidenceSection] = []
    catalog: list[CatalogEntry] = []
    for number in range(7):
        title = f"Alpha {number}" if number < 5 else "Versioned policy"
        parts, entry = document(str(number), title, "cards")
        evidence.extend(parts)
        catalog.append(entry)
    result = select(evidence, catalog, query="alpha")
    assert {item.document_id for item in result.sections} == set(map(str, range(5)))
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.coverage_truncated


def test_oversized_related_group_is_deferred() -> None:
    """A group too large for the entire budget yields honest zero coverage."""
    evidence: list[EvidenceSection] = []
    catalog: list[CatalogEntry] = []
    for number in range(7):
        parts, entry = document(str(number), "Versioned policy", "cards")
        evidence.extend(parts)
        catalog.append(entry)
    result = select(evidence, catalog)
    assert result.mode == "empty" and not result.sections
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.eligible_document_count == 7
    assert result.context.coverage.represented_document_count == 0
    assert result.context.coverage.coverage_truncated


def test_cross_category_related_group_is_selected_once() -> None:
    """A shared title across requested categories cannot duplicate source sections."""
    first, a = document("a", "Shared policy", "accounts")
    second, b = document("b", "SHARED POLICY", "cards")
    result = select(first + second, (a, b), categories=("cards", "accounts"))
    assert len(result.sections) == 2
    assert {item.document_id for item in result.sections} == {"a", "b"}


def test_section_cannot_escape_approved_catalog() -> None:
    """A source/catalog mismatch fails rather than classifying unapproved evidence."""
    evidence, _ = document("unbound", "Card", "cards")
    with pytest.raises(SourceError, match="corpus_changed"):
        select(evidence, ())


def test_uncitable_document_does_not_break_other_category_evidence() -> None:
    """An approved whitespace-only body stays omitted rather than becoming fake evidence."""
    evidence, first = document("first", "Card details", "cards")
    blank = CatalogEntry(document_id="blank", title="No passage", category="cards")
    result = select(evidence, (first, blank))
    assert {item.document_id for item in result.sections} == {"first"}
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.eligible_document_count == 2
    assert result.context.coverage.coverage_truncated
    related = blank.model_copy(update={"title": first.title})
    result = select(evidence, (first, related))
    assert not result.sections
    assert result.context is not None and result.context.coverage is not None
    assert result.context.coverage.coverage_truncated
