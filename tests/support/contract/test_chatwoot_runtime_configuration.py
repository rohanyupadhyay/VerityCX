"""Check optional Chatwoot settings enter the existing typed runtime without weakening defaults."""

from pathlib import Path

import pytest

from veritycx.service.configuration import ConfigurationError, load_configuration


def _settings() -> dict[str, str]:
    """Provide synthetic complete runtime settings without any actual credentials."""
    return {
        "VERITYCX_DATABASE_URL": "synthetic-database",
        "VERITYCX_AUTH_FILE": "synthetic-auth",
        "VERITYCX_CHATWOOT_URL": "http://127.0.0.1:3000",
        "VERITYCX_CHATWOOT_ACCOUNT_ID": "1",
        "VERITYCX_CHATWOOT_INBOX_ID": "2",
        "VERITYCX_CHATWOOT_WEBSITE_TOKEN": "synthetic-public-widget-token",
        "VERITYCX_CHATWOOT_API_TOKEN": "synthetic-private-api-token",
        "VERITYCX_CHATWOOT_BOT_TOKEN": "synthetic-private-bot-token",
        "VERITYCX_CHATWOOT_WEBHOOK_SECRET": "synthetic-private-webhook-secret",
    }


def test_runtime_loads_optional_chatwoot_and_excludes_credentials_from_repr(tmp_path: Path) -> None:
    """Configured chat must reach the API/worker, with secrets omitted from diagnostics."""
    settings = tmp_path / "support.toml"
    settings.write_text("", encoding="utf-8")
    configuration = load_configuration(settings, _settings())
    assert configuration.chatwoot is not None
    assert configuration.chatwoot.inbox_id == 2
    assert "synthetic-private" not in repr(configuration)


def test_partial_chatwoot_configuration_fails_closed(tmp_path: Path) -> None:
    """A partially configured channel must not silently start with broken messaging."""
    settings = tmp_path / "support.toml"
    settings.write_text("", encoding="utf-8")
    values = _settings()
    del values["VERITYCX_CHATWOOT_WEBHOOK_SECRET"]
    with pytest.raises(ConfigurationError, match="invalid_chatwoot_configuration"):
        load_configuration(settings, values)


def test_chatwoot_requires_enough_connections_for_lock_and_transaction(tmp_path: Path) -> None:
    """A one-slot pool must be rejected before the bridge can deadlock on its session lock."""
    settings = tmp_path / "support.toml"
    settings.write_text("pool_max_size=1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid_chatwoot_configuration"):
        load_configuration(settings, _settings())
