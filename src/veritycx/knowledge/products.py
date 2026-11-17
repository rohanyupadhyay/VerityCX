"""Derive conservative product scopes from approved source identifiers, never policy facts."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veritycx.knowledge.catalog import CategoryKey
    from veritycx.knowledge.models import CatalogEntry
    from veritycx.knowledge.nlp import TextNormalizer

# These describe source taxonomy, not products, eligibility, or banking policy.
SOURCE_DOMAINS: tuple[tuple[str, CategoryKey, str, bool], ...] = (
    ("business_checking_accounts", "accounts", "checking", True),
    ("business_savings_accounts", "savings", "savings", True),
    ("business_credit_cards", "cards", "card", True),
    ("checking_accounts", "accounts", "checking", False),
    ("savings_accounts", "savings", "savings", False),
    ("credit_cards", "cards", "card", False),
    ("bank_accounts", "accounts", "account", False),
    ("everyone_pay", "payments", "payment", False),
)
_GENERAL_MODIFIERS = frozenset(
    "a an the my your their our its this that these those which what any all some "
    "personal business customer customers bank banks checking savings credit debit rewards "
    "current new available eligible supported documented different other another existing "
    "monthly annual maintenance replacement foreign payment deposit opening minimum maximum "
    "for of with about to and or no on apply open close in do does is are offers offered "
    "default general linked joint additional multiple several both each certain separate "
    "money funded funding without zero balance fees fee limits limit rate rates interest".split()
)


def product_policy_identity() -> dict[str, object]:
    """Bind source-domain classification and named-product isolation into corpus identity."""
    return {
        "version": 1,
        "domains": SOURCE_DOMAINS,
        "matching": "longest-original-first-pos-audience-v3",
        "general_modifiers": sorted(_GENERAL_MODIFIERS),
    }


def source_category(identifier: str) -> CategoryKey | None:
    """Prefer a known source domain over incidental words in a policy title."""
    return next(
        (
            category
            for domain, category, _, _ in SOURCE_DOMAINS
            if identifier.startswith(f"doc_{domain}_")
        ),
        None,
    )


@dataclass(frozen=True)
class ProductIdentity:
    """Describe a source family and its name aliases without supplying product claims."""

    family: str
    aliases: tuple[str, ...]
    business: bool


def product_identity(identifier: str) -> ProductIdentity | None:
    """Recognize grouped upstream identities; leave generic and authored fixtures unscoped."""
    match = re.fullmatch(r"(doc_(.+))_\d{3}", identifier)
    if match is None or "(general)" in identifier:
        return None
    family = match.group(1)
    for domain, _, kind, business in SOURCE_DOMAINS:
        prefix = f"doc_{domain}_"
        if not family.startswith(prefix):
            continue
        name = _words(family.removeprefix(prefix).replace("_", " "))
        if not name or name in {domain.replace("_", " "), "general"}:
            return None
        if business and not name.startswith("business "):
            name = "business " + name
        aliases = {name}
        if kind in {"savings", "checking"} and name.endswith(" account"):
            stem = name.removesuffix(" account")
            if kind not in stem.split() and "saver" not in stem.split():
                aliases.add(f"{stem} {kind} account")
                aliases.add(f"{stem} {kind}")
        return ProductIdentity(family, tuple(sorted(aliases)), business)
    return None


def _words(text: str) -> str:
    """Normalize punctuation and spacing while preserving whole product-name words."""
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _matches(
    text: str, products: dict[str, ProductIdentity]
) -> tuple[set[str], list[tuple[int, int]]]:
    """Prefer complete longer names over contained names, including business modifiers."""
    matches = [
        (match.start(), match.end(), family)
        for family, product in products.items()
        for alias in product.aliases
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text)
    ]
    retained = [
        item
        for item in matches
        if not any(
            other[0] <= item[0] and item[1] <= other[1] and other[1] - other[0] > item[1] - item[0]
            for other in matches
        )
    ]
    return {item[2] for item in retained}, [(item[0], item[1]) for item in retained]


def _unknown_product(text: str, covered: list[tuple[int, int]], names: set[str]) -> bool:
    """Reject an unmatched named modifier next to a product head instead of dropping it."""
    words = list(re.finditer(r"\w+", text))
    for start, _ in covered:
        modifier = next((word for word in reversed(words) if word.end() <= start), None)
        if modifier is not None and modifier.group() in names - _GENERAL_MODIFIERS:
            return True
    for index, word in enumerate(words):
        if word.group() not in {
            "account",
            "accounts",
            "card",
            "cards",
            "checking",
            "savings",
            "saver",
        }:
            continue
        if any(start <= word.start() < end for start, end in covered) or index == 0:
            continue
        previous = words[index - 1].group()
        if previous in names - _GENERAL_MODIFIERS:
            return True
    return False


def scoped_catalog(
    original: str,
    rewritten: str,
    catalog: Sequence[CatalogEntry],
    *,
    normalizer: TextNormalizer | None = None,
) -> tuple[CatalogEntry, ...]:
    """Keep explicit products and audiences authoritative across rewritten follow-ups."""
    products = {
        product.family: product
        for entry in catalog
        if (product := product_identity(entry.document_id)) is not None
    }
    if not products:
        return tuple(catalog)
    if normalizer is None:
        from veritycx.knowledge.nlp import TextNormalizer

        normalizer = TextNormalizer()
    # Approved title prefixes supply documented display-name variants, not facts.
    for entry in catalog:
        product = product_identity(entry.document_id)
        if product is None:
            continue
        prefix = _words(entry.title.split(":", 1)[0])
        if prefix and any(
            alias == prefix or alias.startswith(prefix + " ") or prefix.startswith(alias + " ")
            for alias in product.aliases
        ):
            current = products[product.family]
            products[product.family] = ProductIdentity(
                product.family, tuple(sorted(set(current.aliases) | {prefix})), product.business
            )
    original_words, rewritten_words = _words(original), _words(rewritten)
    original_matches, original_spans = _matches(original_words, products)
    rewritten_matches, rewritten_spans = _matches(rewritten_words, products)

    def names(text: str) -> set[str]:
        """Use local POS to distinguish product-like names from verbs and status adjectives."""
        return {
            word
            for token in normalizer.analyze(text)
            if token.pos in {"NOUN", "PROPN", "ADJ"}
            and token.lemma not in {"lose", "lost", "steal", "stolen", "expire", "expired"}
            for word in _words(token.surface).split()
        }

    if _unknown_product(original_words, original_spans, names(original)):
        return ()
    if original_matches:
        families = original_matches
    else:
        if _unknown_product(rewritten_words, rewritten_spans, names(rewritten)):
            return ()
        families = rewritten_matches
    original_terms = set(original_words.split())
    query_words = (
        original_terms
        if original_matches or original_terms & {"business", "businesses", "personal"}
        else set(rewritten_words.split())
    )
    business = "business" in query_words or "businesses" in query_words
    personal = "personal" in query_words
    if families and business != personal:
        families = {family for family in families if products[family].business == business}
        if not families:
            return ()
    result: list[CatalogEntry] = []
    for entry in catalog:
        product = product_identity(entry.document_id)
        if families:
            if product is not None and product.family in families:
                result.append(entry)
        elif product is None or business == personal or product.business == business:
            result.append(entry)
    return tuple(result)
