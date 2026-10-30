"""Rank reviewed sections deterministically and bound the supplied evidence/context."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from veritycx.knowledge.models import EvidenceSection
from veritycx.providers.protocol import ContextMessage

if TYPE_CHECKING:
    from veritycx.knowledge.nlp import TextNormalizer
    from veritycx.knowledge.synonyms import SynonymExpander


@dataclass(frozen=True)
class RetrievalSelection:
    """Expose bounded retrieval diagnostics without duplicating source bodies."""

    sections: tuple[EvidenceSection, ...]
    mode: Literal["primary", "synonym", "empty"]
    expanded_term_count: int = 0


def select_evidence(
    original_question: str,
    rewritten_query: str,
    evidence: Sequence[EvidenceSection],
    *,
    normalizer: TextNormalizer,
    expander: SynonymExpander,
) -> RetrievalSelection:
    """Search normalized title/body concepts, expanding only an empty primary result."""
    query_tokens = normalizer.analyze(original_question) + normalizer.analyze(rewritten_query)
    query = frozenset(token.lemma for token in query_tokens if not token.constraint)
    indexed = normalizer.terms_many([item.title + "\n" + item.content for item in evidence])
    frequency: Counter[str] = Counter(term for terms in indexed for term in terms)

    def select(terms: frozenset[str]) -> tuple[EvidenceSection, ...]:
        """Keep the version-one formula and bounds over the version-two representation."""
        ranked = [
            (
                sum(
                    math.log(1 + len(evidence) / (1 + frequency[term]))
                    for term in sorted(terms & words)
                ),
                item,
            )
            for item, words in zip(evidence, indexed, strict=True)
        ]
        ranked.sort(key=lambda pair: (-pair[0], pair[1].document_id, pair[1].section_id))
        selected: list[EvidenceSection] = []
        used = 0
        for score, item in ranked:
            if score <= 0 or len(selected) == 6:
                break
            if used + len(item.content) <= 12000:
                selected.append(item)
                used += len(item.content)
        return tuple(selected)

    primary = select(query)
    if primary:
        return RetrievalSelection(primary, "primary")
    if not query:
        return RetrievalSelection((), "empty")
    expansion = expander.expand(query_tokens, vocabulary=frozenset(frequency))
    fallback = select(frozenset(expansion))
    return RetrievalSelection(fallback, "synonym" if fallback else "empty", len(expansion))


def tokens(text: str) -> set[str]:
    """Extract unique casefolded Unicode alphanumeric runs, excluding underscores."""
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


def retrieve(question: str, evidence: Sequence[EvidenceSection]) -> list[EvidenceSection]:
    """Select at most six positive weighted overlaps with stable ID tie breaks."""
    query = tokens(question)
    tokenized = [tokens(item.content) for item in evidence]
    frequency: Counter[str] = Counter(token for section in tokenized for token in section)
    ranked = [
        (
            sum(
                math.log(1 + len(evidence) / (1 + frequency[token]))
                for token in sorted(query & section)
            ),
            item,
        )
        for item, section in zip(evidence, tokenized, strict=True)
    ]
    ranked.sort(key=lambda pair: (-pair[0], pair[1].document_id, pair[1].section_id))
    selected: list[EvidenceSection] = []
    used = 0
    for score, item in ranked:
        if score <= 0 or len(selected) == 6:
            break
        if used + len(item.content) <= 12000:
            selected.append(item)
            used += len(item.content)
    return selected


def recent_context(messages: Sequence[ContextMessage]) -> tuple[ContextMessage, ...]:
    """Retain the most recent contiguous suffix within the 16000-character budget."""
    selected: list[ContextMessage] = []
    used = 0
    for message in reversed(messages):
        if used + len(message.text) > 16000:
            break
        selected.append(message)
        used += len(message.text)
    return tuple(reversed(selected))
