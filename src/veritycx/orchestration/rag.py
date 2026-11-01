"""Compose explicit language and rewrite dependencies for live or offline workers."""

from dataclasses import dataclass, field
from functools import lru_cache

from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.synonyms import SynonymExpander, WordNetExpander
from veritycx.orchestration.inference import InferenceCapacity
from veritycx.providers.rewrite import DeterministicQueryRewriter, QueryRewriter


@dataclass(frozen=True)
class RAGServices:
    """Keep test substitutes explicit and separate from production failure handling."""

    rewriter: QueryRewriter
    normalizer: TextNormalizer
    expander: SynonymExpander
    inference: InferenceCapacity = field(default_factory=InferenceCapacity)


def create_rag(rewriter: QueryRewriter, *, capacity: int = 10) -> RAGServices:
    """Verify and initialize all local language assets before worker readiness."""
    normalizer = TextNormalizer()
    return RAGServices(
        rewriter, normalizer, WordNetExpander(normalizer), InferenceCapacity(capacity)
    )


@lru_cache(maxsize=1)
def deterministic_rag() -> RAGServices:
    """Explicitly compose offline-authored rewriting with real local retrieval resources."""
    return create_rag(DeterministicQueryRewriter())
