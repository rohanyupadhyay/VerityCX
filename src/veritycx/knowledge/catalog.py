"""Project approved bank documents into public service categories without altering policy facts."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from veritycx.conversations.models import ClosedModel

if TYPE_CHECKING:
    from veritycx.knowledge.models import KnowledgeDocument

CategoryKey = Literal["accounts", "savings", "cards", "payments", "deposits", "other"]
CATEGORIES: dict[CategoryKey, str] = {
    "accounts": "Accounts & everyday banking",
    "savings": "Savings",
    "cards": "Cards",
    "payments": "Payments & transfers",
    "deposits": "Deposits & cash access",
    "other": "Other policies",
}
SYNTHETIC_CATEGORIES: dict[CategoryKey, tuple[int, ...]] = {
    "accounts": (2, 7, 9, 11, 14, 15, 19),
    "savings": (1, 6, 17),
    "cards": (3, 8, 16),
    "payments": (5, 13, 18, 20),
    "deposits": (4, 10, 12),
}
TITLE_CATEGORIES: dict[CategoryKey, tuple[str, ...]] = {
    "cards": ("card", "debit", "credit"),
    "savings": ("savings", "interest"),
    "payments": ("transfer", "wire", "payment", "beneficiary"),
    "deposits": ("deposit", "atm", "cash", "withdrawal"),
    "accounts": ("account", "checking", "statement", "overdraft", "dispute"),
}


class CategoryPolicyIdentity(ClosedModel):
    """Bind discovery behavior to reviewed classification data and priority."""

    policy_version: Literal[1] = 1
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def category_policy_identity() -> CategoryPolicyIdentity:
    """Hash ordered classifier inputs and the related-title grouping policy."""
    payload = {
        "version": 1,
        "categories": list(CATEGORIES.items()),
        "synthetic": list(SYNTHETIC_CATEGORIES.items()),
        "title_rules": list(TITLE_CATEGORIES.items()),
        "related_titles": "casefold-original-title-v1",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return CategoryPolicyIdentity(digest=sha256(raw.encode()).hexdigest())


class PolicySummary(ClosedModel):
    """Expose policy discovery fields only; source paths and hashes are private."""

    id: str
    title: str
    category: str
    excerpt: str
    conflict_ids: tuple[str, ...]
    related_ids: tuple[str, ...]


def category_for(
    document: KnowledgeDocument, mode: Literal["synthetic", "official"]
) -> CategoryKey:
    """Prefer authored synthetic mappings; conservatively classify other titles with a fallback."""
    if mode == "synthetic":
        for category, numbers in SYNTHETIC_CATEGORIES.items():
            if document.id in {f"policy-{number:02}" for number in numbers}:
                return category
    words = set(re.findall(r"\w+", document.title.casefold()))
    return next(
        (category for category, terms in TITLE_CATEGORIES.items() if words.intersection(terms)),
        "other",
    )


def summary_for(
    document: KnowledgeDocument,
    documents: list[KnowledgeDocument],
    mode: Literal["synthetic", "official"],
    query: str = "",
) -> PolicySummary:
    """Build a bounded matching excerpt and retain related versions without resolving conflicts."""
    related = tuple(
        item.id
        for item in documents
        if item.id != document.id and item.title.casefold() == document.title.casefold()
    )
    conflict: tuple[str, ...] = ()
    if mode == "synthetic" and re.fullmatch(r"conflict-(?:0[1-9]|10)-[ab]", document.id):
        counterpart = document.id[:-1] + ("b" if document.id.endswith("a") else "a")
        if counterpart in related:
            conflict = (counterpart,)
    prose = " ".join(document.content.split())
    positions = [prose.casefold().find(term) for term in query.casefold().split()]
    match = min((position for position in positions if position >= 0), default=0)
    start = max(0, match - 65)
    end = start + 240
    excerpt = ("…" if start else "") + prose[start:end] + ("…" if end < len(prose) else "")
    return PolicySummary(
        id=document.id,
        title=document.title,
        category=category_for(document, mode),
        excerpt=excerpt,
        conflict_ids=conflict,
        related_ids=related,
    )
