"""Verify pinned local NLP assets without downloading or loading model code."""

import json
from hashlib import sha256
from importlib.metadata import distribution, version
from pathlib import Path, PurePosixPath

from veritycx import PROJECT_ROOT
from veritycx.conversations.models import ClosedModel

MANIFEST_PATH = PROJECT_ROOT / "config" / "retrieval-resources.json"
WORDNET_PATH = PROJECT_ROOT / ".cache" / "support" / "nlp" / "corpora" / "wordnet.zip"


class ResourceError(ValueError):
    """Expose only a value-free resource failure category."""


class NLPResourceIdentity(ClosedModel):
    """Bind retrieval behavior to installed packages and verified language data."""

    spacy_version: str
    pipeline_name: str
    pipeline_version: str
    pipeline_digest: str
    nltk_version: str
    wordnet_digest: str
    policy_version: int = 2


def resource_manifest() -> dict[str, object]:
    """Read the repository-owned installation inventory."""
    try:
        value: object = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError):
        raise ResourceError("nlp_resources_unavailable") from None


def pipeline_path() -> Path:
    """Locate the installed English pipeline through package metadata."""
    try:
        return Path(str(distribution("en-core-web-sm").locate_file("en_core_web_sm")))
    except Exception:
        raise ResourceError("nlp_resources_unavailable") from None


def configured_identity() -> NLPResourceIdentity:
    """Read public resource metadata without importing or requiring installed NLP assets."""
    try:
        manifest = resource_manifest()
        pipeline, wordnet = manifest["pipeline"], manifest["wordnet"]
        if not isinstance(pipeline, dict) or not isinstance(wordnet, dict):
            raise ValueError
        return NLPResourceIdentity(
            spacy_version=str(manifest["spacy_version"]),
            pipeline_name=str(pipeline["name"]),
            pipeline_version=str(pipeline["version"]),
            pipeline_digest=str(pipeline["sha256"]),
            nltk_version=str(manifest["nltk_version"]),
            wordnet_digest=str(wordnet["sha256"]),
        )
    except Exception:
        raise ResourceError("nlp_resources_unavailable") from None


def verify_resources() -> NLPResourceIdentity:
    """Check installed resource bytes; never fetch assets or import a language pipeline."""
    try:
        manifest = resource_manifest()
        pipeline = manifest["pipeline"]
        wordnet = manifest["wordnet"]
        if not isinstance(pipeline, dict) or not isinstance(wordnet, dict):
            raise ValueError
        for name in ("spacy", "nltk"):
            if version(name) != manifest[f"{name}_version"]:
                raise ValueError
        if version("en-core-web-sm") != pipeline["version"]:
            raise ValueError
        root = pipeline_path()
        files = pipeline["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError
        for relative, expected in files.items():
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError
            target = root / relative
            if target.is_symlink() or sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError
        if WORDNET_PATH.is_symlink():
            raise ValueError
        digest = sha256(WORDNET_PATH.read_bytes()).hexdigest()
        if digest != wordnet["sha256"] or manifest["policy_version"] != 2:
            raise ValueError
        return NLPResourceIdentity(
            spacy_version=str(manifest["spacy_version"]),
            pipeline_name=str(pipeline["name"]),
            pipeline_version=str(pipeline["version"]),
            pipeline_digest=str(pipeline["sha256"]),
            nltk_version=str(manifest["nltk_version"]),
            wordnet_digest=digest,
        )
    except Exception:
        raise ResourceError("nlp_resources_unavailable") from None
