"""Supply bounded English WordNet alternatives only after empty primary selection."""

import warnings
from collections.abc import Sequence
from threading import Lock
from typing import Protocol, cast

from nltk import data as nltk_data
from nltk.corpus.reader.wordnet import WordNetCorpusReader
from nltk.data import ZipFilePathPointer

from veritycx.knowledge.nlp import SearchToken, TextNormalizer
from veritycx.knowledge.resources import WORDNET_PATH, verify_resources


class SynonymExpander(Protocol):
    """Allow deterministic tests without replacing the production selection policy."""

    def expand(
        self, tokens: Sequence[SearchToken], *, vocabulary: frozenset[str]
    ) -> tuple[str, ...]:
        """Return bounded normalized alternatives represented in the approved corpus."""
        ...


class Synset(Protocol):
    """Describe the small typed WordNet interface this application consumes."""

    def lemma_names(self) -> list[str]:
        """Return the lexical alternatives belonging to one particular meaning."""
        ...


class WordNetReader(Protocol):
    """Expose explicit English part-of-speech lookup from verified local data."""

    def synsets(self, word: str, pos: str) -> list[Synset]:
        """Return senses for an English word in the selected grammatical role."""
        ...


class WordNetExpander:
    """Constrain candidate senses by POS, corpus vocabulary, and protected terms."""

    def __init__(self, normalizer: TextNormalizer, reader: WordNetReader | None = None) -> None:
        """Use the pinned local archive unless an explicit test reader is supplied."""
        self.normalizer = normalizer
        self._lock = Lock()
        if reader is None:
            verify_resources()
            # NLTK 3.10 requires explicit authorization even for a direct archive reader.
            # WordNet also resolves its own version mapping under corpora/wordnet.
            # Register only our fixed verified resource directory; never modify the environment.
            data_root = str(WORDNET_PATH.parent.parent)
            if data_root not in nltk_data.path:
                nltk_data.path.append(data_root)
            pointer = ZipFilePathPointer(str(WORDNET_PATH), "wordnet/")
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=(
                        "The multilingual functions are not available with this Wordnet version"
                    ),
                    category=UserWarning,
                    module="nltk.corpus.reader.wordnet",
                )
                reader = cast(WordNetReader, WordNetCorpusReader(pointer, None))
        self.reader = reader

    def expand(
        self, tokens: Sequence[SearchToken], *, vocabulary: frozenset[str]
    ) -> tuple[str, ...]:
        """Use a single surviving sense per concept and at most twelve alternatives."""
        with self._lock:
            return self._expand(tokens, vocabulary=vocabulary)

    def _expand(
        self, tokens: Sequence[SearchToken], *, vocabulary: frozenset[str]
    ) -> tuple[str, ...]:
        """Serialize the reader's mutable seek/cache operations across worker threads."""
        originals = {token.lemma for token in tokens}
        protected = {token.lemma for token in tokens if token.protected or token.constraint}
        expanded: set[str] = set()
        visited: set[str] = set()
        parts = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r"}
        for token in tokens:
            if token.lemma in protected or token.lemma in visited:
                continue
            visited.add(token.lemma)
            pos = parts.get(token.pos)
            if pos is None:
                continue
            surviving: list[set[str]] = []
            for sense in self.reader.synsets(token.lemma, pos):
                candidates: set[str] = set()
                for word in sense.lemma_names():
                    if not word.isalpha():
                        continue
                    terms = self.normalizer.terms(word)
                    if len(terms) == 1:
                        candidates.update(terms & vocabulary - originals)
                if candidates:
                    surviving.append(candidates)
            if len(surviving) == 1:
                expanded.update(sorted(surviving[0])[:3])
            if len(expanded) >= 12:
                break
        return tuple(sorted(expanded)[:12])
