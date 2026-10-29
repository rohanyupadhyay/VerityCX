"""Exercise public policy discovery against real disposable approved documents."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from veritycx import PROJECT_ROOT
from veritycx.knowledge import configuration as corpus_configuration
from veritycx.knowledge import manifest as corpus_manifest
from veritycx.knowledge.manifest import approve, prepare
from veritycx.policy.sources import verified_bytes
from veritycx.service import app as service_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings


@pytest.fixture
def bank_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Use the actual approved loader and ASGI app, without starting a database or provider."""
    root, cache = tmp_path / "documents", tmp_path / "corpus"
    shutil.copytree(PROJECT_ROOT / "tests/support/fixtures/documents", root)
    manifest = prepare(root, cache, "synthetic", "synthetic-v1")
    approve(root, cache, manifest.aggregate_hash)
    monkeypatch.setattr(
        corpus_configuration, "source_mode", lambda mode: (root, cache, "synthetic-v1")
    )
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><title>Bank pages</title>", encoding="utf-8")
    monkeypatch.setattr(service_app, "FRONTEND_ROOT", build)
    auth, _, _ = init_demo(tmp_path / "auth")
    return TestClient(
        service_app.create_app(RuntimeConfiguration(Settings(), SecretStr("dbname=unused"), auth))
    )


def test_all_approved_documents_are_discoverable(bank_client: TestClient) -> None:
    """Paging must retain all documents, including both conflicting versions."""
    identifiers: set[str] = set()
    for page in range(1, 5):
        response = bank_client.get("/bank/api/policies", params={"page": page})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 40
        assert body["page_size"] == 12
        assert body["mode"] == "synthetic"
        assert response.headers["cache-control"] == "no-store"
        identifiers.update(item["id"] for item in body["policies"])
        assert all(
            set(item) == {"id", "title", "category", "excerpt", "conflict_ids", "related_ids"}
            for item in body["policies"]
        )
    assert len(identifiers) == 40
    assert {"conflict-01-a", "conflict-01-b", "policy-20"} <= identifiers
    categories = {item["key"]: item["count"] for item in body["categories"]}
    assert categories["other"] == 20


def test_search_full_text_and_category(bank_client: TestClient) -> None:
    """Search must inspect body text, and category filters must narrow real results."""
    body = bank_client.get("/bank/api/policies", params={"q": "14:00"}).json()
    assert [item["id"] for item in body["policies"]] == ["policy-05"]
    assert "14:00" in body["policies"][0]["excerpt"]
    body = bank_client.get(
        "/bank/api/policies", params={"q": "monthly", "category": "savings"}
    ).json()
    assert [item["id"] for item in body["policies"]] == ["policy-17"]
    assert bank_client.get("/bank/api/policies?q=unfindableword").json()["total"] == 0
    assert bank_client.get("/bank/api/policies?page=99").json()["policies"] == []


def test_full_policy_and_conflicting_versions(bank_client: TestClient) -> None:
    """Details preserve source facts and link known conflicts without resolving them."""
    response = bank_client.get("/bank/api/policies/policy-02")
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == (
        "The synthetic Birch checking monthly fee is 5 synthetic dollars. "
        "This rule applies only to the fictional portfolio demonstration."
    )
    assert body["category"] == "accounts"
    assert body["conflict_ids"] == []
    conflict = bank_client.get("/bank/api/policies/conflict-01-a").json()
    assert conflict["conflict_ids"] == ["conflict-01-b"]
    assert conflict["related_ids"] == ["conflict-01-b"]
    assert "10 days" in conflict["content"]
    assert "20 days" in bank_client.get("/bank/api/policies/conflict-01-b").json()["content"]
    assert "documents/" not in response.text
    assert "sha256" not in body
    assert bank_client.get("/bank/api/policies/not-a-policy").status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=100001",
        "page=abc",
        "category=invalid",
        "q=" + "x" * 201,
        "mode=official",
        "path=../../.env",
    ],
)
def test_invalid_search_cannot_change_sources(bank_client: TestClient, query: str) -> None:
    """Malformed queries and source overrides must be rejected, never interpreted as paths."""
    assert bank_client.get("/bank/api/policies?" + query).status_code == 422


def test_unapproved_and_changed_sources_are_unavailable(
    bank_client: TestClient, tmp_path: Path
) -> None:
    """The public API must fail closed rather than publish stale or unapproved content."""
    source = tmp_path / "documents/policy-02.json"
    source.write_text(
        json.dumps({"id": "policy-02", "title": "Private canary", "content": "unapproved-canary"})
    )
    for url in ["/bank/api/policies", "/bank/api/policies/policy-02"]:
        response = bank_client.get(url)
        assert response.status_code == 503
        assert "unapproved-canary" not in response.text
        assert str(tmp_path) not in response.text
    (tmp_path / "corpus/active").unlink()
    assert bank_client.get("/bank/api/policies").status_code == 503


def test_frontend_deep_links_do_not_swallow_api_errors(bank_client: TestClient) -> None:
    """Explicit website routes refresh correctly; API and unknown paths stay real 404s."""
    for url in ["/bank", "/bank/search?q=fees", "/bank/services/cards", "/bank/policies/policy-02"]:
        response = bank_client.get(url)
        assert response.status_code == 200
        assert "<title>Bank pages</title>" in response.text
    for url in [
        "/bank/api/unknown",
        "/bank/unknown",
        "/bank/services/invalid",
        "/bank/policies",
        "/bank/../../.env",
    ]:
        assert bank_client.get(url).status_code == 404


def test_unclassified_full_documents_and_duplicate_titles(
    bank_client: TestClient, tmp_path: Path
) -> None:
    """Unknown products retain full text and related sources, including IDs containing slashes."""
    content = "# Unclassified details\n\n" + "A long approved paragraph. " * 160 + "Final fact."
    root, cache = tmp_path / "documents", tmp_path / "corpus"
    for suffix in ["one", "two"]:
        (root / f"extra-{suffix}.json").write_text(
            json.dumps({"id": f"custom/{suffix}", "title": "Lunar options", "content": content})
        )
    manifest = prepare(root, cache, "synthetic", "synthetic-v1")
    approve(root, cache, manifest.aggregate_hash)
    response = bank_client.get("/bank/api/policies/custom%2Fone")
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == content
    assert body["category"] == "other"
    assert body["related_ids"] == ["custom/two"]
    assert body["conflict_ids"] == []
    result = bank_client.get("/bank/api/policies?q=Final+fact.").json()
    assert result["total"] == 2
    assert "Final fact." in result["policies"][0]["excerpt"]


def test_source_change_between_inventory_and_read_is_rejected(
    bank_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publication must compare the actual returned bytes with the approved document hash."""
    original = verified_bytes
    calls = 0

    def changed(root: Path, relative: str) -> bytes:
        """Change a single document only on its second read, after inventory verification."""
        nonlocal calls
        raw = original(root, relative)
        if relative == "policy-02.json":
            calls += 1
            if calls == 2:
                return raw.replace(b"5 synthetic", b"9 synthetic")
        return raw

    monkeypatch.setattr(corpus_manifest, "verified_bytes", changed)
    assert bank_client.get("/bank/api/policies/policy-02").status_code == 503
