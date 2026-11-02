"""Keep original corpus hashes verifiable while explicitly preparing ranking version two."""

from pathlib import Path

import pytest

from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import approve, build_manifest, prepare, read_active
from veritycx.knowledge.resources import configured_identity
from veritycx.policy.sources import SourceError


def test_v1_hash_rules_are_unchanged() -> None:
    """Old documents and original metadata still produce their historical identity."""
    root, _, pin = source_mode("synthetic")
    legacy = build_manifest(root, "synthetic", pin, ranking_version=1)
    assert (
        legacy.aggregate_hash == "d93ccecdefc8d84cf264619ef4ebd8ada144db9e0f975d4cc810c33aa8069460"
    )
    assert legacy.ranking_version == 1 and legacy.retrieval_resources is None
    assert legacy.aggregate_hash != build_manifest(root, "synthetic", pin).aggregate_hash


def test_v2_binds_language_resources(tmp_path: Path) -> None:
    """Resource/policy identity participates in hashes independently of source bytes."""
    root, _, pin = source_mode("synthetic")
    identity = configured_identity()
    current = build_manifest(root, "synthetic", pin, ranking_version=2, resource_identity=identity)
    other = build_manifest(
        root,
        "synthetic",
        pin,
        ranking_version=2,
        resource_identity=identity.model_copy(update={"wordnet_digest": "0" * 64}),
    )
    assert current.ranking_version == 2
    assert current.aggregate_hash != other.aggregate_hash
    cache = tmp_path / "corpus"
    prepared = prepare(root, cache, "synthetic", pin)
    with pytest.raises(SourceError, match="missing_sources"):
        read_active(root, cache)
    approve(root, cache, prepared.aggregate_hash)
    assert read_active(root, cache) == prepared


def test_v2_hash_rules_are_unchanged() -> None:
    """The complete lexical baseline keeps its approved identity after category support."""
    root, _, pin = source_mode("synthetic")
    assert build_manifest(root, "synthetic", pin, ranking_version=2).aggregate_hash == (
        "92126bf8d93182482cce66c599890de1db2f66e509dab2bb39a720e6056933b1"
    )
