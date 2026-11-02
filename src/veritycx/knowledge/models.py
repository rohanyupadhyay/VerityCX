"""Validate document envelopes, reviewed provenance and bounded evidence sections."""

from typing import Literal

from pydantic import Field, model_validator

from veritycx.conversations.models import ClosedModel, VersionedModel
from veritycx.knowledge.catalog import CategoryKey, CategoryPolicyIdentity
from veritycx.knowledge.resources import NLPResourceIdentity


class KnowledgeDocument(ClosedModel):
    """Accept exactly the three documented upstream string fields."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class EvidenceRef(ClosedModel):
    """Bind a section to an exact approved corpus and content hash."""

    corpus_version: str
    document_id: str
    section_id: str
    section_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceSection(EvidenceRef):
    """Carry bounded untrusted evidence without granting execution authority."""

    title: str
    content: str = Field(min_length=1, max_length=2000)


class ManifestEntry(ClosedModel):
    """Record reviewed document-only classification and source integrity."""

    path: str
    document_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: Literal["knowledge"] = "knowledge"
    section_ids: tuple[str, ...]


class CatalogEntry(ClosedModel):
    """Bind a full original document title to its approved discovery category."""

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: CategoryKey


class CorpusManifest(VersionedModel):
    """Bind parser and retrieval versions to a reviewed source inventory."""

    corpus_version: str
    source_pin: str
    mode: Literal["synthetic", "official"]
    parser_version: Literal[1] = 1
    ranking_version: Literal[1, 2, 3] = 1
    retrieval_resources: NLPResourceIdentity | None = None
    catalog_index: tuple[CatalogEntry, ...] | None = None
    category_policy: CategoryPolicyIdentity | None = None
    entries: tuple[ManifestEntry, ...]
    aggregate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def versioned_resources(self) -> "CorpusManifest":
        """A version-two identity cannot omit its language resources."""
        if (self.ranking_version >= 2) != (self.retrieval_resources is not None):
            raise ValueError("invalid_retrieval_identity")
        if self.ranking_version == 3:
            if self.catalog_index is None or self.category_policy is None:
                raise ValueError("missing_category_identity")
            identifiers = [entry.document_id for entry in self.catalog_index]
            sources = [entry.document_id for entry in self.entries]
            if (
                len(set(identifiers)) != len(identifiers)
                or len(set(sources)) != len(sources)
                or set(identifiers) != set(sources)
            ):
                raise ValueError("invalid_catalog_inventory")
        elif self.catalog_index is not None or self.category_policy is not None:
            raise ValueError("invalid_legacy_catalog")
        return self
