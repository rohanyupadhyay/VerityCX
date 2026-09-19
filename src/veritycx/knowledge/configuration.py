"""Resolve fixed corpus modes and verify official provenance without reading banking records."""

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from veritycx.data_sources.tau3 import load_tau3_config
from veritycx.knowledge.manifest import load_sections, read_active
from veritycx.knowledge.models import CorpusManifest, EvidenceSection
from veritycx.policy.sources import SourceError
from veritycx.service.configuration import PROJECT_ROOT


def source_mode(mode: Literal["synthetic", "official"]) -> tuple[Path, Path, str]:
    """Resolve fixed source roots and verify the official pin and clean document subtree."""
    cache = PROJECT_ROOT / ".cache" / "support" / "corpora" / mode
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
) -> tuple[CorpusManifest, list[EvidenceSection]]:
    """Return only revalidated reviewed sources bound to the configured mode and pin."""
    root, cache, pin = source_mode(mode)
    manifest = read_active(root, cache)
    if manifest.source_pin != pin or manifest.mode != mode:
        raise SourceError("corpus_changed")
    return manifest, load_sections(root, manifest)
