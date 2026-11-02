"""Select approved category evidence without widening ordinary focused searches."""

import math
from collections import Counter, defaultdict, deque
from collections.abc import Sequence
from dataclasses import replace

from veritycx.knowledge.catalog import CategoryKey
from veritycx.knowledge.models import CatalogEntry, EvidenceSection
from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.retrieval import RetrievalSelection, select_evidence
from veritycx.knowledge.scope import CategoryCoverage, SearchContext, SearchScope
from veritycx.knowledge.synonyms import SynonymExpander
from veritycx.policy.sources import SourceError


def select_scoped_evidence(
    original_question: str,
    rewritten_query: str,
    evidence: Sequence[EvidenceSection],
    *,
    search_scope: SearchScope,
    catalog_index: Sequence[CatalogEntry],
    normalizer: TextNormalizer,
    expander: SynonymExpander,
) -> RetrievalSelection:
    """Retain focused v2 selection or cover complete approved category groups."""
    if search_scope.scope == "focused":
        result = select_evidence(
            original_question, rewritten_query, evidence, normalizer=normalizer, expander=expander
        )
        return replace(result, context=SearchContext(search_scope=search_scope, coverage=None))
    catalog = {entry.document_id: entry for entry in catalog_index}
    if (
        len(catalog) != len(catalog_index)
        or not {item.document_id for item in evidence} <= set(catalog)
        or len({item.section_id for item in evidence}) != len(evidence)
    ):
        raise SourceError("corpus_changed")
    eligible = {
        identifier: entry
        for identifier, entry in catalog.items()
        if entry.category in search_scope.categories
    }
    passages = [item for item in evidence if item.document_id in eligible]
    query = frozenset(
        token.lemma
        for token in normalizer.analyze(original_question) + normalizer.analyze(rewritten_query)
        if not token.constraint
    )
    words = normalizer.terms_many([item.title + "\n" + item.content for item in passages])
    frequency = Counter(term for terms in words for term in terms)
    ranked = [
        (
            sum(
                math.log(1 + len(passages) / (1 + frequency[term]))
                for term in sorted(query & terms)
            ),
            item,
        )
        for item, terms in zip(passages, words, strict=True)
    ]
    ranked.sort(key=lambda pair: (-pair[0], pair[1].document_id, pair[1].section_id))
    by_document: dict[str, list[tuple[float, EvidenceSection]]] = defaultdict(list)
    for pair in ranked:
        by_document[pair[1].document_id].append(pair)
    groups: dict[str, list[str]] = defaultdict(list)
    for identifier, entry in eligible.items():
        groups[entry.title.casefold()].append(identifier)

    def priority(group: tuple[str, ...]) -> tuple[float, str, str]:
        """Keep group ranking independent of input iteration order."""
        best = max(
            (by_document[identifier][0][0] for identifier in group if identifier in by_document),
            default=0.0,
        )
        first = group[0]
        return -best, first, by_document[first][0][1].section_id if first in by_document else ""

    pending: dict[CategoryKey, deque[tuple[str, ...]]] = {
        key: deque() for key in search_scope.categories
    }
    ordered = sorted((tuple(sorted(group)) for group in groups.values()), key=priority)
    for group in ordered:
        owner = next(
            key
            for key in search_scope.categories
            if any(eligible[identifier].category == key for identifier in group)
        )
        pending[owner].append(group)
    selected: list[EvidenceSection] = []
    used = 0
    while any(pending.values()):
        for category in search_scope.categories:
            if not pending[category]:
                continue
            group = pending[category].popleft()
            if any(identifier not in by_document for identifier in group):
                continue
            candidates = [by_document[identifier][0][1] for identifier in group]
            size = sum(len(item.content) for item in candidates)
            if len(selected) + len(candidates) <= 6 and used + size <= 12000:
                selected.extend(candidates)
                used += size
    represented = {item.document_id for item in selected}
    selected_ids = {item.section_id for item in selected}
    for _, item in ranked:
        if len(selected) == 6:
            break
        if (
            item.document_id in represented
            and item.section_id not in selected_ids
            and used + len(item.content) <= 12000
        ):
            selected.append(item)
            selected_ids.add(item.section_id)
            used += len(item.content)
    return RetrievalSelection(
        sections=tuple(selected),
        mode="category" if selected else "empty",
        context=SearchContext(
            search_scope=search_scope,
            coverage=CategoryCoverage(
                eligible_document_count=len(eligible),
                represented_document_count=len(represented),
                coverage_truncated=len(represented) < len(eligible),
            ),
        ),
    )
