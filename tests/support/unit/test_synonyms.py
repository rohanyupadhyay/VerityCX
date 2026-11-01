"""Constrain dictionary senses rather than indiscriminately expanding banking queries."""

from veritycx.knowledge.nlp import SearchToken, TextNormalizer
from veritycx.knowledge.synonyms import Synset, WordNetExpander


class Sense:
    """Expose a fixed authored word sense."""

    def __init__(self, names: list[str]) -> None:
        """Retain the supplied synthetic alternatives."""
        self.names = names

    def lemma_names(self) -> list[str]:
        """Return only this sense's lexical forms."""
        return self.names


class Reader:
    """Provide explicit senses without a global NLTK downloader."""

    def __init__(self, senses: list[Synset]) -> None:
        """Retain synthetic lexical lookup results."""
        self.senses = senses
        self.calls = 0

    def synsets(self, word: str, pos: str) -> list[Synset]:
        """Count only eligible content-word lookups."""
        self.calls += 1
        return self.senses


def test_ambiguous_senses_are_not_expanded() -> None:
    """Multiple corpus-supported meanings must not be flattened into one synonym list."""
    reader = Reader([Sense(["fee"]), Sense(["attack"])])
    expander = WordNetExpander(TextNormalizer(), reader)
    assert (
        expander.expand(
            [SearchToken("charge", "charge", "NOUN", False, False)],
            vocabulary=frozenset({"fee", "attack"}),
        )
        == ()
    )


def test_protected_terms_and_candidate_caps() -> None:
    """Protected words are excluded; alternatives are unique, single-word and bounded."""
    reader = Reader([Sense(["fee", "cost", "price", "rate", "fee", "service_charge"])])
    expander = WordNetExpander(TextNormalizer(), reader)
    protected = [
        SearchToken("Cedar", "cedar", "PROPN", True, False),
        SearchToken("7", "7", "NUM", True, False),
        SearchToken("not", "not", "PART", False, True),
    ]
    vocabulary = frozenset({"fee", "cost", "price", "rate", "service_charge"})
    assert expander.expand(protected, vocabulary=vocabulary) == () and reader.calls == 0
    output = expander.expand(
        [SearchToken("tariff", "tariff", "NOUN", False, False)], vocabulary=vocabulary
    )
    assert output == ("cost", "fee", "price")
    assert len(output) <= 3


def test_real_local_wordnet_lookup() -> None:
    """The production reader loads the pinned local archive, not network data."""
    expander = WordNetExpander(TextNormalizer())
    assert expander.reader.synsets("car", "n")


def test_wordnet_reader_is_serialized_across_worker_threads() -> None:
    """A shared reader must not interleave its mutable file/cache operations."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock

    class ConcurrentReader:
        """Detect overlapping accesses to a single shared corpus reader."""

        def __init__(self) -> None:
            """Initialize the overlap detector."""
            self.active = False
            self.lock = Lock()

        def synsets(self, word: str, pos: str) -> list[Synset]:
            """Model seek/read operations that must form one critical section."""
            with self.lock:
                assert not self.active, "interleaved corpus access"
                self.active = True
            time.sleep(0.02)
            with self.lock:
                self.active = False
            return [Sense(["fee"])]

    reader = ConcurrentReader()
    expander = WordNetExpander(TextNormalizer(), reader)

    def expand(_: int) -> tuple[str, ...]:
        """Run simultaneous empty-result fallback requests."""
        return expander.expand(
            [SearchToken("tariff", "tariff", "NOUN", False, False)],
            vocabulary=frozenset({"fee"}),
        )

    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(expand, range(4))) == [("fee",)] * 4
