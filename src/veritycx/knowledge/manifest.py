"""Prepare and approve exact document inventories; drift never triggers silent repair."""

import json
import os
import stat
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from veritycx.conversations.models import parse_json
from veritycx.knowledge.catalog import category_for, category_policy_identity
from veritycx.knowledge.documents import parse_document
from veritycx.knowledge.index import sections
from veritycx.knowledge.models import (
    CatalogEntry,
    CorpusManifest,
    EvidenceSection,
    KnowledgeDocument,
    ManifestEntry,
)
from veritycx.knowledge.resources import NLPResourceIdentity, configured_identity, verify_resources
from veritycx.policy.sources import SourceError, verified_bytes


def document_paths(root: Path) -> list[str]:
    """Enumerate regular JSON files while refusing linked directory traversal."""
    paths: list[str] = []
    for directory, children, files in os.walk(root, followlinks=False):
        for name in children + files:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise SourceError("forbidden_source")
            if name in files:
                if name == "README.md":
                    continue
                if not stat.S_ISREG(info.st_mode) or path.suffix != ".json":
                    raise SourceError("forbidden_source")
                paths.append(path.relative_to(root).as_posix())
    if not paths:
        raise SourceError("missing_sources")
    return sorted(paths)


def build_manifest(
    root: Path,
    mode: Literal["synthetic", "official"],
    pin: str,
    *,
    ranking_version: Literal[1, 2, 3] = 3,
    resource_identity: NLPResourceIdentity | None = None,
) -> CorpusManifest:
    """Bind hashes, unique IDs and deterministic section IDs to a reviewed provenance pin."""
    entries: list[ManifestEntry] = []
    catalog: list[CatalogEntry] = []
    identifiers: set[str] = set()
    for relative in document_paths(root):
        raw = verified_bytes(root, relative)
        document = parse_document(raw)
        if document.id in identifiers:
            raise SourceError("duplicate_document")
        identifiers.add(document.id)
        if ranking_version == 3:
            catalog.append(
                CatalogEntry(
                    document_id=document.id,
                    title=document.title,
                    category=category_for(document, mode),
                )
            )
        entries.append(
            ManifestEntry(
                path=relative,
                document_id=document.id,
                sha256=sha256(raw).hexdigest(),
                section_ids=tuple(s.section_id for s in sections(document, "pending")),
            )
        )
    identity = (resource_identity or configured_identity()) if ranking_version >= 2 else None
    policy = category_policy_identity() if ranking_version == 3 else None
    payload: dict[str, object] = {
        "mode": mode,
        "pin": pin,
        "parser": 1,
        "ranking": ranking_version,
        "entries": [entry.model_dump() for entry in entries],
    }
    if identity is not None:
        payload["retrieval_resources"] = identity.model_dump()
    if policy is not None:
        payload["category_policy"] = policy.model_dump()
        payload["catalog_index"] = [entry.model_dump() for entry in catalog]
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = sha256(canonical.encode()).hexdigest()
    return CorpusManifest(
        corpus_version=f"{mode}-{digest}",
        source_pin=pin,
        mode=mode,
        ranking_version=ranking_version,
        retrieval_resources=identity,
        category_policy=policy,
        catalog_index=tuple(catalog) if ranking_version == 3 else None,
        entries=tuple(entries),
        aggregate_hash=digest,
    )


def prepare(
    root: Path, cache: Path, mode: Literal["synthetic", "official"], pin: str
) -> CorpusManifest:
    """Create an immutable pending manifest/index; no automatic activation is permitted."""
    manifest = build_manifest(root, mode, pin, resource_identity=verify_resources())
    directory = cache / manifest.aggregate_hash
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "manifest.json"
    if target.exists():
        if load_manifest(target) != manifest:
            raise SourceError("corpus_changed")
    else:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(manifest.model_dump_json())
        indexed = load_sections(root, manifest)
        with (directory / "index.json").open("x", encoding="utf-8") as stream:
            json.dump([s.model_dump() for s in indexed], stream)
    return manifest


def load_manifest(path: Path) -> CorpusManifest:
    """Validate the complete stored manifest before interpreting its paths or identity."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("manifest_limit")
        parse_json(raw)
        return CorpusManifest.model_validate_json(raw)
    except (OSError, ValueError, ValidationError):
        raise SourceError("corpus_changed") from None


def approve(root: Path, cache: Path, digest: str) -> None:
    """Activate only an unchanged prepared hash; caller fixes the source root and mode."""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise SourceError("invalid_manifest_hash")
    manifest = load_manifest(cache / digest / "manifest.json")
    if (
        manifest.aggregate_hash != digest
        or build_manifest(
            root,
            manifest.mode,
            manifest.source_pin,
            ranking_version=manifest.ranking_version,
            resource_identity=manifest.retrieval_resources,
        )
        != manifest
    ):
        raise SourceError("corpus_changed")
    temporary = cache / "active.pending"
    temporary.write_text(digest, encoding="ascii")
    temporary.replace(cache / "active")


def read_active(root: Path, cache: Path) -> CorpusManifest:
    """Revalidate reviewed identity and bytes before using any active source inventory."""
    try:
        digest = (cache / "active").read_text(encoding="ascii")
    except OSError:
        raise SourceError("missing_sources") from None
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise SourceError("corpus_changed")
    manifest = load_manifest(cache / digest / "manifest.json")
    if (
        manifest.aggregate_hash != digest
        or build_manifest(
            root,
            manifest.mode,
            manifest.source_pin,
            ranking_version=manifest.ranking_version,
            resource_identity=manifest.retrieval_resources,
        )
        != manifest
    ):
        raise SourceError("corpus_changed")
    return manifest


def load_documents(root: Path, manifest: CorpusManifest) -> list[KnowledgeDocument]:
    """Load complete documents only after matching approved hashes, IDs, and section inventory."""
    result: list[KnowledgeDocument] = []
    for entry in manifest.entries:
        raw = verified_bytes(root, entry.path)
        if sha256(raw).hexdigest() != entry.sha256:
            raise SourceError("corpus_changed")
        document = parse_document(raw)
        indexed = sections(document, manifest.corpus_version)
        if (
            document.id != entry.document_id
            or tuple(s.section_id for s in indexed) != entry.section_ids
        ):
            raise SourceError("corpus_changed")
        result.append(document)
    return result


def load_sections(root: Path, manifest: CorpusManifest) -> list[EvidenceSection]:
    """Use verified source bytes, never trust a potentially modified derived index."""
    return [
        section
        for document in load_documents(root, manifest)
        for section in sections(document, manifest.corpus_version)
    ]
