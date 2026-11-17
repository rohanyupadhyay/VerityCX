"""Exclude explicitly staff-only sources from customer discovery and retrieval."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veritycx.knowledge.models import KnowledgeDocument

# Only audience labels count: ordinary internal transfers are customer-facing policies.
TITLE_LABEL = r"\binternal\b(?=\s*(?:[:)\]\-\u2013\u2014|]|$))"
RESTRICTED_USE = (
    r"\b(?:staff|agents?|internal)(?:[\s_\-\u2013\u2014]+use)?[\s_\-\u2013\u2014]+only\b"
)


def audience_policy_identity() -> dict[str, object]:
    """Bind exact audience rules and matching semantics into reviewed corpus policy identity."""
    return {
        "version": 1,
        "title_label": TITLE_LABEL,
        "restricted_use": RESTRICTED_USE,
        "matching": "casefold-regex-search-whole-document-v1",
    }


def customer_facing(document: KnowledgeDocument) -> bool:
    """Deny a whole source with an internal title label or explicit restricted-use marking."""
    title = document.title.casefold()
    return not (
        re.search(TITLE_LABEL, title)
        or re.search(RESTRICTED_USE, title)
        or re.search(RESTRICTED_USE, document.content.casefold())
    )
