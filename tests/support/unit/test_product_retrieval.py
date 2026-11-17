"""Keep named products isolated and diversify discovery using authored structured identities."""

from collections.abc import Sequence

import pytest

from veritycx.knowledge.catalog import category_for
from veritycx.knowledge.category_retrieval import select_scoped_evidence
from veritycx.knowledge.index import sections
from veritycx.knowledge.models import CatalogEntry, EvidenceSection, KnowledgeDocument
from veritycx.knowledge.nlp import SearchToken, TextNormalizer
from veritycx.knowledge.retrieval import RetrievalSelection
from veritycx.knowledge.scope import SearchScope


class NoExpansion:
    """Return no lexical alternatives, keeping these fixtures independent of WordNet."""

    def expand(
        self, tokens: Sequence[SearchToken], *, vocabulary: frozenset[str]
    ) -> tuple[str, ...]:
        """Provide a finite empty fallback without network or model calls."""
        return ()


def select(
    documents: list[KnowledgeDocument], original: str, rewritten: str, *, overview: bool = False
) -> RetrievalSelection:
    """Run the real scoped selector with reviewed fixture metadata and local NLP."""
    corpus: list[EvidenceSection] = [part for doc in documents for part in sections(doc, "fixture")]
    return select_scoped_evidence(
        original,
        rewritten,
        corpus,
        search_scope=SearchScope(
            scope="category_overview" if overview else "focused",
            categories=("cards",) if overview else (),
        ),
        catalog_index=[
            CatalogEntry(document_id=d.id, title=d.title, category=category_for(d, "official"))
            for d in documents
        ],
        normalizer=TextNormalizer(),
        expander=NoExpansion(),
    )


def test_followup_cannot_mix_personal_and_business_products() -> None:
    """A resolved personal savings reference must exclude similarly named business procedures."""
    documents = [
        KnowledgeDocument(
            id="doc_savings_accounts_amber_account_001",
            title="Amber Savings Account: Complete Guide",
            content="You can open Amber Savings with no initial deposit. Monthly fee: zero.",
        ),
        KnowledgeDocument(
            id="doc_business_savings_accounts_amber_saver_account_001",
            title="Business Amber Saver: Opening your account",
            content="Open the business savings account now and deposit funds within thirty days.",
        ),
    ]
    result = select(
        documents,
        "Can I open it without depositing any money?",
        "Can I open the Amber Savings Account without depositing any money?",
    )
    assert result.sections
    assert {part.document_id for part in result.sections} == {
        "doc_savings_accounts_amber_account_001"
    }


@pytest.mark.parametrize("name,slug", [("Blue", "blue"), ("Light Blue", "light_blue")])
def test_longest_product_name_preserves_modifiers(name: str, slug: str) -> None:
    """A shorter colour name cannot steal another product's identity or facts."""
    documents = [
        KnowledgeDocument(
            id=f"doc_checking_accounts_{product}_account_001",
            title=f"{title} Account specifications",
            content=f"The {title} Account has its own balance requirement and purchase limit.",
        )
        for product, title in [("blue", "Blue"), ("light_blue", "Light Blue")]
    ]
    query = f"What balance requirement and purchase limit apply to the {name} Account?"
    result = select(documents, query, query)
    assert {part.document_id for part in result.sections} == {
        f"doc_checking_accounts_{slug}_account_001"
    }


@pytest.mark.parametrize(
    "question", ["What are the Birch checking fees?", "What is the Cedar card fee?"]
)
def test_unknown_named_product_cannot_borrow_other_product_facts(question: str) -> None:
    """Generic fee overlap cannot turn an absent product into an apparently supported one."""
    documents = [
        KnowledgeDocument(
            id="doc_checking_accounts_blue_account_001",
            title="Blue Account fees",
            content="Checking account maintenance fees and card fees are documented here.",
        )
    ]
    assert select(documents, question, question).sections == ()


def test_source_domain_wins_over_incidental_card_words() -> None:
    """A savings benefit mentioning a card must not displace actual cards from discovery."""
    document = KnowledgeDocument(
        id="doc_savings_accounts_amber_account_009",
        title="Amber Account: Platinum Rewards Card holder benefits",
        content="A savings policy describing linked-product benefits.",
    )
    assert category_for(document, "official") == "savings"


def test_card_discovery_covers_distinct_products_before_more_details() -> None:
    """A product with many detail documents cannot consume the entire discovery budget."""
    documents = [
        KnowledgeDocument(
            id=f"doc_credit_cards_{product}_rewards_card_{number:03}",
            title=f"{product.title()} Rewards Card: {'Guide' if number == 1 else 'Details'}",
            content="Credit card products available to customers. " * 2,
        )
        for product in ("amber", "cobalt", "jade", "pearl")
        for number in range(1, 4)
    ]
    result = select(
        documents,
        "Which credit cards are available?",
        "Which credit cards are available?",
        overview=True,
    )
    families = {part.document_id.rsplit("_", 1)[0] for part in result.sections}
    assert families == {
        f"doc_credit_cards_{product}_rewards_card"
        for product in ("amber", "cobalt", "jade", "pearl")
    }
    assert {f"{family}_001" for family in families} <= {
        part.document_id for part in result.sections
    }
    assert len(result.sections) <= 6


@pytest.mark.parametrize(
    "question", ["What should I do with a lost card?", "How do I compare cards?"]
)
def test_generic_card_phrasing_is_not_an_unknown_product(question: str) -> None:
    """Ordinary verbs and status adjectives must not be mistaken for product names."""
    documents = [
        KnowledgeDocument(
            id="doc_credit_cards_amber_rewards_card_001",
            title="Amber Rewards Card: Guide",
            content="Compare cards by their benefits. Contact support if your card is lost.",
        )
    ]
    assert select(documents, question, question).sections


@pytest.mark.parametrize(
    "name", ["Dark Blue Account", "Ultra Blue Account", "dark blue account", "ultra blue account"]
)
def test_unknown_modifier_cannot_be_dropped_from_a_known_name(name: str) -> None:
    """An unknown longer product name must not inherit the shorter product's policy."""
    documents = [
        KnowledgeDocument(
            id="doc_checking_accounts_blue_account_001",
            title="Blue Account fees",
            content="Blue Account fee policy.",
        )
    ]
    query = f"What are the {name} fees?"
    assert select(documents, query, query).sections == ()


@pytest.mark.parametrize(
    "name,slug",
    [
        ("Green Fee-Free Account", "green_fee-free_account"),
        ("Green Account (checking)", "green_account_(checking)"),
    ],
)
def test_documented_punctuation_is_preserved_in_product_names(name: str, slug: str) -> None:
    """Display-name punctuation and source slug punctuation use the same normalization."""
    documents = [
        KnowledgeDocument(
            id=f"doc_checking_accounts_{slug}_001",
            title=f"{name}: Guide",
            content="Documented account fees.",
        )
    ]
    query = f"What are the {name} fees?"
    assert select(documents, query, query).sections


def test_business_qualifier_cannot_select_personal_product() -> None:
    """Matching a bare personal product name cannot erase an explicit business constraint."""
    documents = [
        KnowledgeDocument(
            id="doc_checking_accounts_blue_account_001",
            title="Blue Account",
            content="Personal account benefits.",
        )
    ]
    query = "What are the benefits of business Blue Account?"
    assert select(documents, query, query).sections == ()


def test_explicit_business_topic_change_rejects_a_stale_personal_rewrite() -> None:
    """The current audience request must remain authoritative over prior personal context."""
    documents = [
        KnowledgeDocument(
            id="doc_savings_accounts_amber_account_001",
            title="Amber Savings Account",
            content="Personal savings account benefits.",
        ),
        KnowledgeDocument(
            id="doc_business_savings_accounts_amber_saver_account_001",
            title="Business Amber Saver: Guide",
            content="Business savings account benefits.",
        ),
    ]
    result = select(
        documents, "What about a business account?", "What are the Amber Savings Account benefits?"
    )
    assert all("business_" in part.document_id for part in result.sections)


def test_documented_business_short_name_is_resolved() -> None:
    """A full name from an approved title need not repeat an absent source-slug suffix."""
    documents = [
        KnowledgeDocument(
            id="doc_business_savings_accounts_amber_saver_account_001",
            title="Business Amber Saver: Complete Guide",
            content="Business account fees.",
        )
    ]
    query = "What are the Business Amber Saver fees?"
    assert select(documents, query, query).sections
