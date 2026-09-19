"""Rank reviewed sections deterministically and bound the supplied evidence/context."""

import math
import re
from collections import Counter
from collections.abc import Sequence

from veritycx.knowledge.models import EvidenceSection
from veritycx.providers.protocol import ContextMessage


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
