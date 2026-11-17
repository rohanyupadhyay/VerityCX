"""Initialize pinned customer-app knowledge while preserving invalid existing data."""

import os
import subprocess
import sys
from typing import Literal

from veritycx.data_sources.tau3 import setup_tau3_data
from veritycx.knowledge import configuration
from veritycx.knowledge.manifest import approve, prepare
from veritycx.knowledge.models import CorpusManifest
from veritycx.knowledge.resources import WORDNET_PATH, ResourceError, verify_resources
from veritycx.policy.sources import SourceError


def _ensure_resources() -> None:
    """Reuse valid NLP assets or run the pinned installer; altered assets are never replaced."""
    try:
        verify_resources()
    except ResourceError:
        # Path.exists() treats dangling links as absent; the installer must never
        # replace any existing invalid resource, including that case.
        if os.path.lexists(WORDNET_PATH):
            raise ResourceError("nlp_resources_unavailable") from None
        result = subprocess.run(  # noqa: S603 - fixed project-owned installer, no shell.
            [
                sys.executable,
                str(configuration.PROJECT_ROOT / "scripts" / "setup_retrieval_resources.py"),
            ],
            cwd=configuration.PROJECT_ROOT,
            check=False,
        )
        if result.returncode:
            raise ResourceError("nlp_resources_unavailable") from None
        verify_resources()


def ensure_corpus(mode: Literal["synthetic", "official"]) -> CorpusManifest:
    """Acquire missing assets and activate a missing corpus under startup authorization.

    Existing checkouts and active manifests must pass their original validation. Initial
    activation is serialized with an exclusively owned lock; failures preserve the source
    and any existing approval. Only the configured documents subtree is indexed, and no
    model calls are made. Low-level API/worker startup never invokes this initializer.
    """
    if mode == "official":
        setup_tau3_data(configuration.PROJECT_ROOT)
    _ensure_resources()
    root, cache, pin = configuration.source_mode(mode)
    active = cache / "active"
    if os.path.lexists(active):
        return configuration.active_corpus(mode)[0]
    cache.mkdir(parents=True, exist_ok=True)
    lock = cache / "startup.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SourceError("corpus_setup_in_progress") from None
    try:
        # Another startup may have completed between the first observation and our lock.
        if not os.path.lexists(active):
            manifest = prepare(root, cache, mode, pin)
            approve(root, cache, manifest.aggregate_hash)
        return configuration.active_corpus(mode)[0]
    finally:
        os.close(descriptor)
        lock.unlink()
