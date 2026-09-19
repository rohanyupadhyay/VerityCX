"""Reject unapproved, malformed, changed and linked knowledge sources."""

import json
from pathlib import Path

import pytest

from veritycx.knowledge.documents import read_document
from veritycx.knowledge.manifest import approve, prepare, read_active
from veritycx.policy.sources import SourceError


def test_closed_document(tmp_path: Path) -> None:
    """Only closed document envelopes inside the permitted root may be parsed."""
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"id": "policy", "title": "Policy", "content": "Synthetic policy"}))
    assert read_document(tmp_path, "policy.json").id == "policy"
    for body in [
        '{"id":"x","title":"x","content":"x","grading":"secret"}',
        '{"id":"x","id":"y","title":"x","content":"x"}',
        "x" * (1024 * 1024 + 1),
    ]:
        path.write_text(body)
        with pytest.raises(SourceError):
            read_document(tmp_path, "policy.json")
    with pytest.raises(SourceError):
        read_document(tmp_path, "../policy.json")


def test_manifest_approval_and_drift(tmp_path: Path) -> None:
    """Approval binds bytes, unique document IDs and corpus identity."""
    source, cache = tmp_path / "documents", tmp_path / "cache"
    source.mkdir()
    path = source / "policy.json"
    path.write_text(json.dumps({"id": "policy", "title": "Policy", "content": "Synthetic policy"}))
    manifest = prepare(source, cache, "synthetic", "synthetic-v1")
    approve(source, cache, manifest.aggregate_hash)
    assert read_active(source, cache).aggregate_hash == manifest.aggregate_hash
    path.write_text(json.dumps({"id": "policy", "title": "Policy", "content": "Changed"}))
    with pytest.raises(SourceError, match="corpus_changed"):
        read_active(source, cache)
    with pytest.raises(SourceError, match="corpus_changed"):
        approve(source, cache, manifest.aggregate_hash)


def test_duplicate_ids_and_manifest_substitution(tmp_path: Path) -> None:
    """A renamed or altered source cannot bypass unique IDs and approved byte hashes."""
    source, cache = tmp_path / "documents", tmp_path / "cache"
    source.mkdir()
    body = json.dumps({"id": "same", "title": "Policy", "content": "Synthetic"})
    (source / "one.json").write_text(body)
    (source / "two.json").write_text(body)
    with pytest.raises(SourceError, match="duplicate_document"):
        prepare(source, cache, "synthetic", "fixture")
    (source / "two.json").unlink()
    manifest = prepare(source, cache, "synthetic", "fixture")
    approve(source, cache, manifest.aggregate_hash)
    altered = manifest.model_dump(mode="json")
    altered["source_pin"] = "forged-pin"
    (cache / manifest.aggregate_hash / "manifest.json").write_text(json.dumps(altered))
    with pytest.raises(SourceError, match="corpus_changed"):
        read_active(source, cache)


def test_link_component_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Inspect link metadata before opening even when the host cannot create actual symlinks."""
    import os
    import stat

    path = tmp_path / "policy.json"
    path.write_text('{"id":"x","title":"x","content":"x"}')
    original = Path.lstat

    def linked(candidate: Path) -> os.stat_result:
        """Simulate a link at the final component without following or opening it."""
        value = original(candidate)
        if candidate == path:
            fields = list(value)
            fields[0] = stat.S_IFLNK | 0o777
            return os.stat_result(fields)
        return value

    monkeypatch.setattr(Path, "lstat", linked)
    with pytest.raises(SourceError, match="forbidden_source"):
        read_document(tmp_path, "policy.json")
