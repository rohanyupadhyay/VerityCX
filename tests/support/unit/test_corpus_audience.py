"""Keep staff-only source material out of customer documents and retrieval evidence."""

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Literal

import pytest

from veritycx.knowledge.documents import read_document
from veritycx.knowledge.index import sections
from veritycx.knowledge.manifest import build_manifest, load_documents, load_sections, read_active
from veritycx.knowledge.models import CorpusManifest, ManifestEntry
from veritycx.policy.sources import SourceError


def write_document(root: Path, identifier: str, title: str, content: str) -> None:
    """Write authored source envelopes without importing upstream document content."""
    (root / f"{identifier}.json").write_text(
        json.dumps({"id": identifier, "title": title, "content": content}), encoding="utf-8"
    )


def historical_manifest(root: Path) -> CorpusManifest:
    """Recreate the legacy hash contract for a reviewed inventory without audience filtering."""
    entries: list[ManifestEntry] = []
    for path in sorted(root.glob("*.json")):
        document = read_document(root, path.name)
        entries.append(
            ManifestEntry(
                path=path.name,
                document_id=document.id,
                sha256=sha256(path.read_bytes()).hexdigest(),
                section_ids=tuple(section.section_id for section in sections(document, "pending")),
            )
        )
    payload = {
        "mode": "synthetic",
        "pin": "fixture",
        "parser": 1,
        "ranking": 1,
        "entries": [entry.model_dump() for entry in entries],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return CorpusManifest(
        corpus_version=f"synthetic-{digest}",
        source_pin="fixture",
        mode="synthetic",
        entries=tuple(entries),
        aggregate_hash=digest,
    )


@pytest.mark.parametrize("ranking_version", [1, 2, 3])
@pytest.mark.parametrize(
    "title,content",
    [
        ("Internal: Account assistance", "staff-canary"),
        ("Account assistance (INTERNAL)", "staff-canary"),
        ("Account assistance [Internal]", "staff-canary"),
        ("Account assistance — Internal", "staff-canary"),
        ("Staff-only account assistance", "staff-canary"),
        ("Agent only account assistance", "staff-canary"),
        ("Account assistance", "For STAFF ONLY. staff-canary"),
        ("Account assistance", "For agent-only use. staff-canary"),
        ("Customer protections", "Public guidance.\n\n## Internal use only\n\nstaff-canary"),
        ("Account assistance", "Internal-use-only. staff-canary"),
    ],
)
def test_staff_sources_are_excluded_before_indexing(
    tmp_path: Path,
    title: str,
    content: str,
    ranking_version: Literal[1, 2, 3],
) -> None:
    """Explicit staff markings exclude a whole document in every supported retrieval version."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    write_document(tmp_path, "private", title, content)
    manifest = build_manifest(tmp_path, "synthetic", "fixture", ranking_version=ranking_version)
    assert [entry.document_id for entry in manifest.entries] == ["public"]
    assert [document.id for document in load_documents(tmp_path, manifest)] == ["public"]
    evidence = load_sections(tmp_path, manifest)
    assert evidence and {section.document_id for section in evidence} == {"public"}
    assert all("staff-canary" not in section.content for section in evidence)
    if manifest.catalog_index is not None:
        assert [entry.document_id for entry in manifest.catalog_index] == ["public"]


def test_public_internal_transfer_language_is_retained(tmp_path: Path) -> None:
    """Ordinary public transfer wording is not an internal-audience label."""
    content = "You can request an internal transfer between your own accounts."
    write_document(tmp_path, "public", "Internal transfers between your accounts", content)
    manifest = build_manifest(tmp_path, "official", "fixture")
    assert [document.content for document in load_documents(tmp_path, manifest)] == [content]
    assert load_sections(tmp_path, manifest)[0].document_id == "public"


def test_all_staff_sources_are_missing_customer_sources(tmp_path: Path) -> None:
    """An inventory with no eligible customer documents cannot be prepared or indexed."""
    write_document(tmp_path, "private", "Internal: Account assistance", "staff-canary")
    with pytest.raises(SourceError, match="missing_sources"):
        build_manifest(tmp_path, "synthetic", "fixture")


def test_denied_documents_still_require_unique_ids(tmp_path: Path) -> None:
    """Filtering must not conceal duplicate identifiers in the original source tree."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    (tmp_path / "private.json").write_text(
        json.dumps({"id": "public", "title": "Internal: Help", "content": "staff-canary"})
    )
    with pytest.raises(SourceError, match="duplicate_document"):
        build_manifest(tmp_path, "synthetic", "fixture")


def test_denied_documents_still_require_valid_envelopes(tmp_path: Path) -> None:
    """An audience marker cannot bypass the closed upstream schema."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    (tmp_path / "private.json").write_text(
        json.dumps(
            {"id": "private", "title": "Internal: Help", "content": "staff-canary", "extra": True}
        )
    )
    with pytest.raises(SourceError, match="invalid_document"):
        build_manifest(tmp_path, "synthetic", "fixture")


def test_denied_documents_still_require_safe_paths(tmp_path: Path) -> None:
    """Linked staff sources must fail source validation rather than silently disappearing."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    write_document(tmp_path, "private", "Internal: Help", "staff-canary")
    try:
        (tmp_path / "linked.json").symlink_to(tmp_path / "private.json")
    except OSError:
        pytest.skip("Host does not permit file symlinks")
    with pytest.raises(SourceError, match="forbidden_source"):
        build_manifest(tmp_path, "synthetic", "fixture")


@pytest.mark.parametrize("load", [load_documents, load_sections])
def test_historical_unsafe_inventories_cannot_load_staff_material(
    tmp_path: Path, load: Callable[[Path, CorpusManifest], object]
) -> None:
    """Even valid source hashes in an old manifest cannot authorize staff-only document reads."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    write_document(tmp_path, "private", "Internal: Help", "staff-canary")
    manifest = historical_manifest(tmp_path)
    with pytest.raises(SourceError, match="forbidden_source"):
        load(tmp_path, manifest)


def test_historical_unsafe_active_inventory_requires_new_approval(tmp_path: Path) -> None:
    """Revalidation rejects an unsafe old inventory without silently changing the active pointer."""
    root, cache = tmp_path / "documents", tmp_path / "cache"
    root.mkdir()
    write_document(root, "public", "Savings fees", "A public policy.")
    write_document(root, "private", "Internal: Help", "staff-canary")
    manifest = historical_manifest(root)
    directory = cache / manifest.aggregate_hash
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(manifest.model_dump_json())
    active = cache / "active"
    active.write_text(manifest.aggregate_hash)
    with pytest.raises(SourceError, match="corpus_changed"):
        read_active(root, cache)
    assert active.read_text() == manifest.aggregate_hash


def test_approved_public_document_cannot_be_replaced_with_staff_content(tmp_path: Path) -> None:
    """Changing audience markings after approval is still source-byte tampering."""
    write_document(tmp_path, "public", "Savings fees", "A public policy.")
    manifest = build_manifest(tmp_path, "synthetic", "fixture")
    write_document(tmp_path, "public", "Savings fees", "Staff-only. staff-canary")
    with pytest.raises(SourceError, match="corpus_changed"):
        load_documents(tmp_path, manifest)
