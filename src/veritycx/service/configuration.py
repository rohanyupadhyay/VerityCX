"""Load closed local settings; separate runtime secrets from migration credentials."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ConfigurationError(ValueError):
    """Report a fixed startup category without leaking settings or credentials."""


class Settings(BaseModel):
    """Validate nonsecret limits and fixed local deployment constraints."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)
    provider: Literal["deterministic", "openai"] = "deterministic"
    model: Literal["gpt-4.1-mini-2025-04-14"] = "gpt-4.1-mini-2025-04-14"
    corpus_mode: Literal["synthetic", "official"] = "synthetic"
    bind: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    worker_concurrency: int = Field(default=10, ge=1, le=10)
    pool_max_size: int = Field(default=20, ge=1, le=20)
    lease_seconds: Literal[30] = 30
    heartbeat_seconds: Literal[5] = 5
    work_scan_seconds: Literal[1] = 1
    processing_seconds: Literal[60] = 60
    provider_attempts: Literal[2] = 2
    message_chars: Literal[8000] = 8000
    conversation_messages: Literal[100] = 100
    retention_days: Literal[30] = 30
    purge_interval_seconds: Literal[3600] = 3600
    traces_enabled: bool = False

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject boolean values that compare equal to numeric Literal defaults."""
        if isinstance(value, dict):
            for key, item in value.items():
                if key != "traces_enabled" and isinstance(item, bool):
                    raise ValueError("invalid_setting_type")
        return value


@dataclass(frozen=True)
class RuntimeConfiguration:
    """Carry only runtime-required configuration; never include an admin DSN."""

    settings: Settings
    database_url: SecretStr = field(repr=False)
    auth_file: Path = field(repr=False)
    provider_key: SecretStr | None = field(default=None, repr=False)
    trace_key: SecretStr | None = field(default=None, repr=False)
    trace_project: str | None = field(default=None, repr=False)


def load_configuration(
    path: Path,
    env: Mapping[str, str],
    *,
    provider: str | None = None,
    corpus_mode: str | None = None,
) -> RuntimeConfiguration:
    """Read root-relative TOML and approved overrides, raising sanitized categories."""
    try:
        with (PROJECT_ROOT / path).open("rb") as stream:
            values = tomllib.load(stream)
        if provider is not None:
            values["provider"] = provider
        if corpus_mode is not None:
            values["corpus_mode"] = corpus_mode
        settings = Settings.model_validate(values)
    except (OSError, ValueError, ValidationError):
        raise ConfigurationError("invalid_configuration") from None
    provider_key = env.get("OPENAI_API_KEY") if settings.provider == "openai" else None
    if settings.provider == "openai" and not provider_key:
        raise ConfigurationError("missing_provider_credential")
    trace_key = env.get("LANGSMITH_API_KEY") if settings.traces_enabled else None
    project = env.get("LANGSMITH_PROJECT") if settings.traces_enabled else None
    if settings.traces_enabled and (not trace_key or not project):
        raise ConfigurationError("missing_trace_configuration")
    database_url = env.get("VERITYCX_DATABASE_URL")
    auth_file = env.get("VERITYCX_AUTH_FILE")
    if not database_url or not auth_file:
        raise ConfigurationError("missing_runtime_configuration")
    return RuntimeConfiguration(
        settings,
        SecretStr(database_url),
        (PROJECT_ROOT / auth_file).resolve(),
        SecretStr(provider_key) if provider_key else None,
        SecretStr(trace_key) if trace_key else None,
        project,
    )
