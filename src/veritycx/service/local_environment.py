"""Share private, non-overwriting dotenv generation between maintained setup commands."""

from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv.parser import parse_stream


class LocalSetupError(ValueError):
    """Expose one safe local-setup failure category without credentials."""


def _app_environment_content(path: Path, values: dict[str, str]) -> str:
    """Fill empty dotenv assignments and reject conflicts without changing the file."""
    # The application's dotenv loader interpolates even single-quoted ${...} strings.
    # Refuse such generated values instead of silently changing a DSN or auth path.
    if path.is_symlink() or any("${" in value for value in values.values()):
        raise LocalSetupError("local_support_app_configuration_conflict")
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    seen: set[str] = set()
    parts: list[str] = []
    for binding in parse_stream(StringIO(content)):
        if binding.error:
            raise LocalSetupError("local_support_app_configuration_conflict")
        key = binding.key
        if key in values:
            if key in seen or binding.value not in (None, "", values[key]):
                raise LocalSetupError("local_support_app_configuration_conflict")
            seen.add(key)
            if not binding.value:
                parts.append(f"{key}={_dotenv_quote(values[key])}\n")
                continue
        parts.append(binding.original.string)
    result = "".join(parts)
    if result and not result.endswith("\n"):
        result += "\n"
    for key, value in values.items():
        if key not in seen:
            result += f"{key}={_dotenv_quote(value)}\n"
    return result


def _dotenv_quote(value: str) -> str:
    """Quote a validated literal dotenv value without invoking a shell."""
    # Generated DSNs and paths must round-trip through python-dotenv's single quotes.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _write_app_environment(path: Path, values: dict[str, str]) -> None:
    """Atomically fill local app settings while preserving existing nonempty values."""
    content = _app_environment_content(path, values)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        path.chmod(0o600)
        return
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
