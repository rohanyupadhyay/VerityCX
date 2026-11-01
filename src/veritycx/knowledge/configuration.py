"""Resolve fixed corpus modes and verify official provenance without reading banking records."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from psycopg.conninfo import conninfo_to_dict

from veritycx.data_sources.tau3 import load_tau3_config
from veritycx.knowledge.manifest import load_documents, load_sections, read_active
from veritycx.knowledge.models import CorpusManifest, EvidenceSection, KnowledgeDocument
from veritycx.knowledge.resources import configured_identity
from veritycx.policy.sources import SourceError
from veritycx.service.configuration import PROJECT_ROOT


def corpus_cache(mode: Literal["synthetic", "official"], *, validation: bool = False) -> Path:
    """Select the same fixed namespace for preparation, approval, and runtime reads."""
    try:
        database = conninfo_to_dict(os.environ.get("VERITYCX_DATABASE_URL", ""))
        validation = validation or (
            database.get("dbname") == "veritycx_support_test"
            and database.get("host") in {"127.0.0.1", "::1"}
        )
    except Exception:
        validation = bool(validation)
    cache_name = f"test-{mode}" if validation else mode
    return PROJECT_ROOT / ".cache" / "support" / "corpora" / cache_name


def source_mode(
    mode: Literal["synthetic", "official"], *, validation: bool = False
) -> tuple[Path, Path, str]:
    """Resolve fixed source roots and verify the official pin and clean document subtree."""
    cache = corpus_cache(mode, validation=validation)
    if mode == "synthetic":
        return PROJECT_ROOT / "tests" / "support" / "fixtures" / "documents", cache, "synthetic-v1"
    configuration = load_tau3_config(PROJECT_ROOT)
    checkout = PROJECT_ROOT / configuration.paths.checkout
    root = PROJECT_ROOT / configuration.paths.documents
    pin = configuration.upstream.commit_sha
    git = shutil.which("git")
    if git is None:
        raise SourceError("corpus_changed")
    try:
        head = subprocess.run(  # noqa: S603 - fixed Git arguments and repository-owned paths.
            [git, "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        changed = subprocess.run(  # noqa: S603 - fixed read-only Git command; no shell.
            [
                git,
                "-C",
                str(checkout),
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                str(root.relative_to(checkout)),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise SourceError("corpus_changed") from None
    if head.stdout.strip() != pin or changed.stdout.strip():
        raise SourceError("corpus_changed")
    return root, cache, pin


def active_corpus(
    mode: Literal["synthetic", "official"],
    *,
    validation: bool = False,
) -> tuple[CorpusManifest, list[EvidenceSection]]:
    """Return only revalidated reviewed sources bound to the configured mode and pin."""
    root, cache, pin = source_mode(mode, validation=True) if validation else source_mode(mode)
    manifest = read_active(root, cache)
    if manifest.source_pin != pin or manifest.mode != mode:
        raise SourceError("corpus_changed")
    if manifest.ranking_version != 2 or manifest.retrieval_resources != configured_identity():
        raise SourceError("retrieval_upgrade_required")
    return manifest, load_sections(root, manifest)


def active_documents(
    mode: Literal["synthetic", "official"],
) -> tuple[CorpusManifest, list[KnowledgeDocument]]:
    """Return complete approved documents, rechecking provenance and bytes on every call."""
    root, cache, pin = source_mode(mode)
    manifest = read_active(root, cache)
    if manifest.source_pin != pin or manifest.mode != mode:
        raise SourceError("corpus_changed")
    return manifest, load_documents(root, manifest)
