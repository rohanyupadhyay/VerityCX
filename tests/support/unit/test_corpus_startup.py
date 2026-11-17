"""Exercise automatic corpus activation, offline reuse, and preservation on startup failure."""

import json
from pathlib import Path
from typing import Literal

import pytest

from veritycx.knowledge import configuration
from veritycx.policy.sources import SourceError


@pytest.fixture
def startup_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use real source/manifest operations inside a disposable project root."""
    monkeypatch.setattr(configuration, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("VERITYCX_DATABASE_URL", raising=False)
    root = tmp_path / "tests/support/fixtures/documents"
    root.mkdir(parents=True)
    (root / "policy.json").write_text(
        json.dumps(
            {"id": "policy-01", "title": "Savings policy", "content": "Opening deposit: 50."}
        )
    )
    return root


def test_startup_activates_missing_corpus_once(startup_documents: Path) -> None:
    """First startup makes source documents retrievable; subsequent starts do not rewrite state."""
    from veritycx.knowledge.startup import ensure_corpus

    first = ensure_corpus("synthetic")
    manifest, evidence = configuration.active_corpus("synthetic")
    assert first == manifest
    assert [entry.document_id for entry in manifest.entries] == ["policy-01"]
    assert [section.content for section in evidence] == ["Opening deposit: 50."]
    cache = configuration.corpus_cache("synthetic")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in cache.rglob("*") if p.is_file()}
    assert ensure_corpus("synthetic") == first
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in cache.rglob("*") if p.is_file()}
    assert after == before


def test_startup_preserves_changed_approved_corpus(startup_documents: Path) -> None:
    """Changed approved sources must fail rather than silently gain a new approval."""
    from veritycx.knowledge.startup import ensure_corpus

    ensure_corpus("synthetic")
    active = configuration.corpus_cache("synthetic") / "active"
    previous = active.read_bytes()
    document = startup_documents / "policy.json"
    document.write_text('{"id":"policy-01","title":"Savings policy","content":"Changed policy."}')
    with pytest.raises(SourceError, match="corpus_changed"):
        ensure_corpus("synthetic")
    assert active.read_bytes() == previous
    assert "Changed policy." in document.read_text()


def test_invalid_initial_document_is_not_activated(startup_documents: Path) -> None:
    """An invalid source envelope leaves no active corpus or owned initialization lock."""
    from veritycx.knowledge.startup import ensure_corpus

    (startup_documents / "policy.json").write_text('{"grading":"forbidden"}')
    with pytest.raises(SourceError, match="invalid_document"):
        ensure_corpus("synthetic")
    cache = configuration.corpus_cache("synthetic")
    assert not (cache / "active").exists()
    assert not (cache / "startup.lock").exists()


def test_startup_preserves_another_initializers_lock(startup_documents: Path) -> None:
    """A second initializer cannot activate a corpus or remove somebody else's lock."""
    from veritycx.knowledge.startup import ensure_corpus

    cache = configuration.corpus_cache("synthetic")
    cache.mkdir(parents=True)
    lock = cache / "startup.lock"
    lock.write_text("another initializer")
    with pytest.raises(SourceError, match="corpus_setup_in_progress"):
        ensure_corpus("synthetic")
    assert lock.read_text() == "another initializer"
    assert not (cache / "active").exists()


def test_official_startup_acquires_before_loading_only_documents(
    startup_documents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acquisition must finish before official activation; adjacent state/tasks are excluded."""
    from veritycx.knowledge import startup

    cache = configuration.corpus_cache("official")
    acquired: list[Path] = []

    def acquire(root: Path) -> None:
        """Stand in only for the separately tested external Git acquisition."""
        acquired.append(root)

    def sources(mode: Literal["synthetic", "official"]) -> tuple[Path, Path, str]:
        """Expose the temporary approved root only after acquisition has happened."""
        assert mode == "official"
        assert acquired == [configuration.PROJECT_ROOT]
        return startup_documents, cache, "official-fixture-pin"

    (startup_documents.parent / "db.json").write_text('{"private":"not knowledge"}')
    tasks = startup_documents.parent / "tasks"
    tasks.mkdir()
    (tasks / "task.json").write_text('{"expected_answer":"not knowledge"}')
    monkeypatch.setattr(startup, "setup_tau3_data", acquire)
    monkeypatch.setattr(configuration, "source_mode", sources)
    manifest = startup.ensure_corpus("official")
    assert manifest.mode == "official"
    assert manifest.source_pin == "official-fixture-pin"
    assert [entry.path for entry in manifest.entries] == ["policy.json"]


def test_failed_acquisition_cannot_activate_or_fall_back(
    startup_documents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network/acquisition error must not select synthetic data or write official approval."""
    from veritycx.data_sources.tau3 import Tau3OperationError
    from veritycx.knowledge import startup

    def unavailable(root: Path) -> None:
        """Simulate an external download failure before source access."""
        raise Tau3OperationError("clone-failed", "Download unavailable")

    monkeypatch.setattr(startup, "setup_tau3_data", unavailable)
    with pytest.raises(Tau3OperationError, match="Download unavailable"):
        startup.ensure_corpus("official")
    assert not (configuration.corpus_cache("official") / "active").exists()
    assert not (configuration.corpus_cache("synthetic") / "active").exists()


def test_missing_resources_are_installed_before_activation(
    startup_documents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing language asset invokes the installer and is checked again before activation."""
    from veritycx.knowledge import startup
    from veritycx.knowledge.resources import NLPResourceIdentity, ResourceError, configured_identity

    marker = configuration.PROJECT_ROOT / "installed"
    scripts = configuration.PROJECT_ROOT / "scripts"
    scripts.mkdir()
    (scripts / "setup_retrieval_resources.py").write_text(
        "from pathlib import Path\n"
        "(Path(__file__).resolve().parents[1] / 'installed').write_text('ready')\n"
    )

    def resources() -> NLPResourceIdentity:
        """Represent asset readiness through a real child-written installation marker."""
        if not marker.exists():
            raise ResourceError("nlp_resources_unavailable")
        return configured_identity()

    monkeypatch.setattr(startup, "verify_resources", resources)
    monkeypatch.setattr(startup, "WORDNET_PATH", marker, raising=False)
    manifest = startup.ensure_corpus("synthetic")
    assert marker.read_text() == "ready"
    assert [entry.document_id for entry in manifest.entries] == ["policy-01"]
    # Reuse must not invoke the installer once its assets verify.
    (scripts / "setup_retrieval_resources.py").write_text("raise SystemExit(1)\n")
    assert startup.ensure_corpus("synthetic") == manifest


def test_resource_install_failure_does_not_activate_corpus(
    startup_documents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing external installer must stop initialization before any corpus is approved."""
    from veritycx.knowledge import startup
    from veritycx.knowledge.resources import NLPResourceIdentity, ResourceError

    scripts = configuration.PROJECT_ROOT / "scripts"
    scripts.mkdir()
    (scripts / "setup_retrieval_resources.py").write_text("raise SystemExit(1)\n")

    def unavailable() -> NLPResourceIdentity:
        """Represent absent/invalid local language data without touching installed assets."""
        raise ResourceError("nlp_resources_unavailable")

    monkeypatch.setattr(startup, "verify_resources", unavailable)
    monkeypatch.setattr(
        startup, "WORDNET_PATH", configuration.PROJECT_ROOT / "missing", raising=False
    )
    with pytest.raises(ResourceError, match="nlp_resources_unavailable"):
        startup.ensure_corpus("synthetic")
    assert not (configuration.corpus_cache("synthetic") / "active").exists()


@pytest.mark.parametrize("kind", ["regular", "dangling_symlink"])
def test_invalid_existing_language_asset_never_invokes_installer(
    startup_documents: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Even a dangling resource link is existing invalid state and must not be replaced."""
    from veritycx.knowledge import startup
    from veritycx.knowledge.resources import NLPResourceIdentity, ResourceError

    root = configuration.PROJECT_ROOT
    asset = root / "wordnet.zip"
    if kind == "regular":
        asset.write_bytes(b"invalid asset")
    else:
        try:
            asset.symlink_to(root / "missing-target")
        except OSError:
            pytest.skip("Host does not permit file symlinks")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "setup_retrieval_resources.py").write_text(
        "from pathlib import Path\n"
        "(Path(__file__).resolve().parents[1] / 'installer-ran').write_text('unexpected')\n"
    )

    def unavailable() -> NLPResourceIdentity:
        """Represent failed byte/type validation of the temporary resource."""
        raise ResourceError("nlp_resources_unavailable")

    monkeypatch.setattr(startup, "verify_resources", unavailable)
    monkeypatch.setattr(startup, "WORDNET_PATH", asset, raising=False)
    with pytest.raises(ResourceError, match="nlp_resources_unavailable"):
        startup.ensure_corpus("synthetic")
    assert not (root / "installer-ran").exists()
    assert (
        asset.is_symlink() if kind == "dangling_symlink" else asset.read_bytes() == b"invalid asset"
    )
