"""Verify reproducible local NLP resources without request-time networking."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from veritycx.service.configuration import Settings


def test_rewrite_model_defaults_to_answer_model() -> None:
    """Rewriting defaults to the configured answering snapshot."""
    assert Settings().effective_rewrite_model == Settings().model


def test_explicit_rewrite_model_is_independent() -> None:
    """Only the rewrite stage uses the independent override."""
    settings = Settings(rewrite_model="rewrite-fixture")
    assert settings.effective_rewrite_model == "rewrite-fixture"
    assert settings.model == Settings().model
    with pytest.raises(ValidationError):
        Settings(rewrite_model=" ")


def test_resource_identity_is_verified() -> None:
    """Installed assets match the reviewed resource hashes."""
    from veritycx.knowledge.resources import verify_resources

    identity = verify_resources()
    assert identity.pipeline_name == "en_core_web_sm"
    assert len(identity.wordnet_digest) == 64
    assert identity.policy_version == 2


def test_missing_resources_fail_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing local assets fail without exposing their private path."""
    from veritycx.knowledge import resources

    monkeypatch.setattr(resources, "WORDNET_PATH", tmp_path / "private-secret.zip")
    with pytest.raises(resources.ResourceError, match="nlp_resources_unavailable") as error:
        resources.verify_resources()
    assert "private-secret" not in str(error.value)


def test_request_path_never_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resource checks never make network requests."""
    import urllib.request

    from veritycx.knowledge.resources import verify_resources

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("request-time network")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    assert verify_resources().pipeline_name == "en_core_web_sm"
