"""Normalize searchable English concepts while preserving original source text."""

from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from veritycx.knowledge.resources import NLPResourceIdentity, pipeline_path, verify_resources

CONSTRAINTS = frozenset(
    {
        "no",
        "not",
        "never",
        "nor",
        "without",
        "before",
        "after",
        "less",
        "more",
        "than",
        "under",
        "over",
    }
)
_INFERENCE_LOCK = Lock()


@dataclass(frozen=True)
class SearchToken:
    """Retain enough linguistic information to constrain lexical expansion."""

    surface: str
    lemma: str
    pos: str
    protected: bool
    constraint: bool


@lru_cache(maxsize=1)
def _pipeline() -> tuple[Language, NLPResourceIdentity]:
    """Load the verified POS and lemma pipeline once per process."""
    identity = verify_resources()
    data = pipeline_path() / f"{identity.pipeline_name}-{identity.pipeline_version}"
    return spacy.load(data, exclude=["parser", "ner", "senter"]), identity


class TextNormalizer:
    """Provide one shared representation for query, title, and passage text."""

    def __init__(self) -> None:
        """Initialize the process-local language pipeline before claiming work."""
        self.pipeline, self.identity = _pipeline()
        self._passages: OrderedDict[str, frozenset[str]] = OrderedDict()

    def analyze(self, text: str) -> tuple[SearchToken, ...]:
        """Preserve protected constraints and remove noninformative language tokens."""
        with _INFERENCE_LOCK:
            doc = self.pipeline(text)
        return self._tokens(doc)

    @staticmethod
    def _tokens(doc: Doc) -> tuple[SearchToken, ...]:
        """Convert model annotations into a bounded application-owned representation."""
        result: list[SearchToken] = []
        for index, token in enumerate(doc):
            if not any(character.isalnum() for character in token.text):
                continue
            surface = token.text
            lower = surface.casefold()
            constraint = lower in CONSTRAINTS or token.dep_ == "neg"
            numeric = token.like_num or any(character.isdigit() for character in surface)
            # Product modifiers such as "Cedar card" can be tagged as common nouns.
            # Preserve capitalized singular modifiers without exempting plural "Fees".
            named_modifier = (
                token.pos_ == "NOUN"
                and surface.istitle()
                and (token.lemma_ or surface).casefold() == lower
                and index + 1 < len(doc)
                and doc[index + 1].pos_ == "NOUN"
            )
            protected = numeric or token.pos_ == "PROPN" or named_modifier
            if token.is_stop and not constraint and not numeric:
                continue
            lemma = lower if protected or constraint else (token.lemma_ or surface).casefold()
            result.append(SearchToken(surface, lemma, token.pos_, protected, constraint))
        return tuple(result)

    def terms(self, text: str) -> frozenset[str]:
        """Return relevance-bearing concepts; constraints alone cannot retrieve evidence."""
        return frozenset(token.lemma for token in self.analyze(text) if not token.constraint)

    def terms_many(self, texts: list[str]) -> list[frozenset[str]]:
        """Cache at most 4096 verified passage representations; never cache query text."""
        with _INFERENCE_LOCK:
            # Snapshot current hits: later insertions may evict them within a large batch.
            known = {text: self._passages[text] for text in texts if text in self._passages}
            missing = list(dict.fromkeys(text for text in texts if text not in self._passages))
            computed = {
                text: frozenset(token.lemma for token in self._tokens(doc) if not token.constraint)
                for text, doc in zip(
                    missing, self.pipeline.pipe(missing, batch_size=32), strict=True
                )
            }
            computed.update(known)
            result: list[frozenset[str]] = []
            for text in texts:
                terms = computed[text]
                self._passages[text] = terms
                self._passages.move_to_end(text)
                if len(self._passages) > 4096:
                    self._passages.popitem(last=False)
                result.append(terms)
            return result
