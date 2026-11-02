"""Pin the shared category snapshot and strict search-scope contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veritycx.knowledge import catalog, configuration
from veritycx.knowledge.catalog import CATEGORIES, category_for, category_policy_identity
from veritycx.knowledge.documents import parse_document
from veritycx.knowledge.manifest import approve, build_manifest, prepare, read_active
from veritycx.knowledge.models import CatalogEntry, CorpusManifest
from veritycx.knowledge.scope import (
    CategoryCoverage,
    SearchContext,
    SearchScope,
    category_hints,
)
from veritycx.policy.sources import SourceError


def test_catalog_matches_bank_categories() -> None:
    """Discovery uses full-document categories, including the non-card Pine title."""
    root, _, pin = configuration.source_mode("synthetic")
    manifest = build_manifest(root, "synthetic", pin)
    assert manifest.ranking_version == 3 and manifest.catalog_index is not None
    assert manifest.category_policy == category_policy_identity()
    entries = {item.document_id: item for item in manifest.catalog_index}
    assert {key for key, item in entries.items() if item.category == "cards"} == {
        "policy-03",
        "policy-08",
        "policy-16",
    }
    for source in manifest.entries:
        document = parse_document((root / source.path).read_bytes())
        assert entries[document.id].category == category_for(document, "synthetic")
        assert entries[document.id].title == document.title
    assert [hint.key for hint in category_hints(manifest.catalog_index)] == list(CATEGORIES)


def test_heading_does_not_change_catalog_assignment(tmp_path: Path) -> None:
    """A category-looking first heading cannot override the original document title."""
    (tmp_path / "policy.json").write_text(
        json.dumps(
            {"id": "custom", "title": "Operating terms", "content": "# Card details\n\nA policy."}
        )
    )
    manifest = build_manifest(tmp_path, "synthetic", "fixture")
    assert manifest.catalog_index == (
        CatalogEntry(document_id="custom", title="Operating terms", category="other"),
    )


@pytest.mark.parametrize("change", ["duplicate", "foreign", "missing", "category", "absent"])
def test_catalog_inventory_is_closed(change: str) -> None:
    """A version-three catalog must cover exactly the approved document IDs."""
    root, _, pin = configuration.source_mode("synthetic")
    payload = build_manifest(root, "synthetic", pin).model_dump(mode="json")
    entries = payload["catalog_index"]
    if change == "duplicate":
        entries.append(entries[0])
    elif change == "foreign":
        entries[0]["document_id"] = "foreign"
    elif change == "missing":
        entries.pop()
    elif change == "category":
        entries[0]["category"] = "unknown-category"
    else:
        payload["catalog_index"] = None
    with pytest.raises(ValidationError):
        CorpusManifest.model_validate_json(json.dumps(payload))


def test_category_policy_drift_requires_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing classification data invalidates a prepared and approved snapshot."""
    root, _, pin = configuration.source_mode("synthetic")
    prepared = prepare(root, tmp_path, "synthetic", pin)
    assert not (tmp_path / "active").exists()
    approve(root, tmp_path, prepared.aggregate_hash)
    before = category_policy_identity()
    monkeypatch.setitem(catalog.TITLE_CATEGORIES, "cards", ("different-word",))
    assert category_policy_identity() != before
    with pytest.raises(SourceError, match="corpus_changed"):
        read_active(root, tmp_path)


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_browsing_remains_but_chat_requires_v3(
    version: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy manifests remain inspectable and cannot silently gain category behavior."""
    root, _, pin = configuration.source_mode("synthetic")
    legacy = build_manifest(root, "synthetic", pin, ranking_version=version)  # type: ignore[arg-type]
    directory = tmp_path / legacy.aggregate_hash
    directory.mkdir()
    (directory / "manifest.json").write_text(legacy.model_dump_json())
    approve(root, tmp_path, legacy.aggregate_hash)
    monkeypatch.setattr(configuration, "source_mode", lambda mode: (root, tmp_path, pin))
    assert configuration.active_documents("synthetic")[0] == legacy
    with pytest.raises(SourceError, match="retrieval_upgrade_required"):
        configuration.active_corpus("synthetic")


@pytest.mark.parametrize(
    "scope,categories",
    [
        ("focused", ["cards"]),
        ("category_overview", []),
        ("category_overview", ["cards", "cards"]),
        ("category_overview", ["loans"]),
    ],
)
def test_scope_rejects_inconsistent_or_unknown_categories(
    scope: str, categories: list[str]
) -> None:
    """The model can choose only a distinct, bounded category scope."""
    with pytest.raises(ValidationError):
        SearchScope.model_validate_json(json.dumps({"scope": scope, "categories": categories}))


def test_scope_canonical_order_and_empty_known_categories() -> None:
    """Canonical order is server-owned; a known category need not have source documents."""
    value = SearchScope(scope="category_overview", categories=("cards", "accounts"))
    assert value.categories == ("accounts", "cards")
    assert category_hints(()) == ()
    assert SearchScope(scope="category_overview", categories=("cards",)).categories == ("cards",)


@pytest.mark.parametrize(
    "eligible,represented,truncated",
    [
        (-1, 0, False),
        (1, 2, False),
        (2, 1, False),
        (1, 1, True),
    ],
)
def test_coverage_is_measured_consistently(
    eligible: int, represented: int, truncated: bool
) -> None:
    """Coverage counts cannot overstate completeness or document membership."""
    with pytest.raises(ValidationError):
        CategoryCoverage(
            eligible_document_count=eligible,
            represented_document_count=represented,
            coverage_truncated=truncated,
        )


def test_context_requires_coverage_only_for_overviews() -> None:
    """Ordinary focused searches do not claim measured category coverage."""
    overview = SearchScope(scope="category_overview", categories=("cards",))
    focused = SearchScope(scope="focused", categories=())
    coverage = CategoryCoverage(
        eligible_document_count=0, represented_document_count=0, coverage_truncated=False
    )
    with pytest.raises(ValidationError):
        SearchContext(search_scope=overview, coverage=None)
    with pytest.raises(ValidationError):
        SearchContext(search_scope=focused, coverage=coverage)
    assert SearchContext(search_scope=overview, coverage=coverage).coverage == coverage
