"""Exercise closed settings, approved overrides and safe startup failures."""

from pathlib import Path

import pytest

from veritycx.service.configuration import ConfigurationError, load_configuration


@pytest.mark.parametrize(
    "text",
    [
        'unknown = "canary-secret"',
        'bind = "0.0.0.0"',
        "worker_concurrency = true",
        "provider_attempts = 3",
        "pool_max_size = 21",
    ],
)
def test_invalid_settings(tmp_path: Path, text: str) -> None:
    """Reject unknown keys and reviewed limits without echoing submitted values."""
    path = tmp_path / "support.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        load_configuration(path, {})
    assert "canary-secret" not in str(error.value)


def test_live_requires_credentials(tmp_path: Path) -> None:
    """Explicit live mode must fail instead of falling back to fixtures."""
    path = tmp_path / "support.toml"
    path.write_text('provider = "openai"', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="missing_provider_credential"):
        load_configuration(path, {})


def test_defaults_and_admin_isolation(tmp_path: Path) -> None:
    """Runtime configuration accepts explicit secrets but excludes the admin DSN."""
    path = tmp_path / "support.toml"
    path.write_text("", encoding="utf-8")
    env = {
        "VERITYCX_DATABASE_URL": "host=127.0.0.1 dbname=veritycx_support",
        "VERITYCX_AUTH_FILE": ".cache/support/auth.json",
        "VERITYCX_MIGRATION_DATABASE_URL": "admin-secret",
    }
    config = load_configuration(path, env)
    assert config.settings.provider == "deterministic"
    assert config.settings.work_scan_seconds == 1
    assert "admin-secret" not in repr(config)
    assert "host=" not in repr(config)


def test_approved_overrides(tmp_path: Path) -> None:
    """Only named provider and corpus overrides alter loaded nonsecret settings."""
    path = tmp_path / "support.toml"
    path.write_text("", encoding="utf-8")
    env = {
        "VERITYCX_DATABASE_URL": "host=127.0.0.1 dbname=veritycx_support",
        "VERITYCX_AUTH_FILE": ".cache/support/auth.json",
        "OPENAI_API_KEY": "test-canary",
    }
    result = load_configuration(path, env, provider="openai", corpus_mode="official")
    assert result.settings.provider == "openai"
    assert result.settings.corpus_mode == "official"
    assert "test-canary" not in repr(result)
