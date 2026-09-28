"""Load optional developer configuration from the single repository root."""

from dotenv import load_dotenv
from dotenv.parser import parse_stream

from veritycx import PROJECT_ROOT as PROJECT_ROOT


class EnvironmentLoadError(RuntimeError):
    """Report a fixed dotenv failure category without exposing configuration values."""


def load_project_environment() -> None:
    """Load ``<project-root>/.env`` without replacing explicit process values.

    A missing file is intentionally a no-op. Malformed or unreadable files raise a
    value-independent category so callers cannot accidentally disclose secrets.
    """
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8") as stream:
            if any(binding.error for binding in parse_stream(stream)):
                raise EnvironmentLoadError("invalid_environment_file")
        load_dotenv(dotenv_path=path, override=False)
    except EnvironmentLoadError:
        raise
    except (OSError, UnicodeError):
        raise EnvironmentLoadError("invalid_environment_file") from None
