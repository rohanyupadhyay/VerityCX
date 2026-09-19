"""Validate document envelopes, reviewed provenance and bounded evidence sections."""

from typing import Literal

from pydantic import Field

from veritycx.conversations.models import ClosedModel, VersionedModel


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


class CorpusManifest(VersionedModel):
    """Bind parser and retrieval versions to a reviewed source inventory."""

    corpus_version: str
    source_pin: str
    mode: Literal["synthetic", "official"]
    parser_version: Literal[1] = 1
    ranking_version: Literal[1] = 1
    entries: tuple[ManifestEntry, ...]
    aggregate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
