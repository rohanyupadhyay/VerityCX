"""Check public frontend delivery without exposing private runtime configuration."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from veritycx.service import app as service_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Construct the real app with disposable credentials and a controlled build root."""
    auth, _, _ = init_demo(tmp_path / "auth")
    monkeypatch.setattr(service_app, "FRONTEND_ROOT", tmp_path / "dist", raising=False)
    configuration = RuntimeConfiguration(
        Settings(),
        SecretStr("host=127.0.0.1 dbname=synthetic"),
        auth,
        SecretStr("synthetic-provider-canary"),
    )
    return TestClient(service_app.create_app(configuration))


def test_customer_page_serves_built_index_without_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening the app URL must return the built customer page, never embedded secrets."""
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / "index.html").write_text(
        "<!doctype html><title>VerityCX support</title>", encoding="utf-8"
    )
    client = _client(tmp_path, monkeypatch)
    response = client.get("/")
    assert response.status_code == 200
    assert "VerityCX support" in response.text
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "synthetic-provider-canary" not in response.text


def test_customer_page_reports_unbuilt_frontend_without_breaking_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing frontend build must be explicit while backend liveness remains usable."""
    client = _client(tmp_path, monkeypatch)
    response = client.get("/")
    assert response.status_code == 503
    assert response.json() == {"status": "frontend_unavailable"}
    assert client.get("/health/live").status_code == 200


def test_customer_assets_are_public_and_cannot_read_outside_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only built assets may be read; private configuration must stay outside the mount."""
    directory = tmp_path / "dist" / "assets"
    directory.mkdir(parents=True)
    (directory / "app-123.js").write_text("console.info('synthetic asset');", encoding="utf-8")
    (tmp_path / ".env").write_text("PRIVATE=synthetic-canary", encoding="utf-8")
    client = _client(tmp_path, monkeypatch)
    assert client.get("/assets/app-123.js").status_code == 200
    assert client.get("/assets/../../.env").status_code == 404
    assert client.get("/.env").status_code == 404


def test_widget_configuration_is_disabled_without_integration_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unconfigured customer chat must have an explicit closed public response."""
    client = _client(tmp_path, monkeypatch)
    response = client.get("/chat/config")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "base_url": None, "website_token": None}
    assert "synthetic-provider-canary" not in response.text
