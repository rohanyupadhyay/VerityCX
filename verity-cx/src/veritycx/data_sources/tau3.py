"""Acquire and inspect the pinned tau3-Banking dependency without disclosure.

This module owns the typed configuration boundary, path containment, Git and filesystem
validation, setup transaction, and safe inspection summaries for Feature 001.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path, PurePosixPath, PureWindowsPath

_CONFIG_RELATIVE_PATH = Path("config/tau3-bench.toml")
_EXPECTED_REPOSITORY_URL = "https://github.com/sierra-research/tau2-bench.git"
_EXPECTED_LICENSE = "MIT"
_EXPECTED_TAG = "v1.0.1"
_EXPECTED_COMMIT_SHA = "fc0055dc4e0a316c3f83133267fbd6faaa770992"
_EXPECTED_PATHS = {
    "checkout": ".cache/tau3-bench/",
    "documents": ".cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/",
    "database": ".cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json",
    "tasks": ".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/",
}
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_GIT_VERSION_PATTERN = re.compile(r"^git version (\d+)\.(\d+)(?:\.\d+)?")
_MINIMUM_GIT_VERSION = (2, 34)
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class Tau3OperationError(Exception):
    """Represent an expected, categorized, and sanitized tau3 operation failure."""

    category: str
    message: str
    path: Path | None

    def __init__(self, category: str, message: str, path: Path | None = None) -> None:
        """Initialize an expected failure with safe public context.

        Args:
            category: Stable machine-assertable error category.
            message: Sanitized human-readable failure and recovery guidance.
            path: Optional configured or current-run-owned path relevant to the failure.
        """
        super().__init__(message)
        self.category = category
        self.message = message
        self.path = path


@dataclass(frozen=True, slots=True)
class Tau3UpstreamConfig:
    """Store the immutable upstream repository identity."""

    repository_url: str
    license_id: str
    tag: str
    commit_sha: str


@dataclass(frozen=True, slots=True)
class Tau3PathConfig:
    """Store reviewed project-relative checkout and banking-data paths."""

    checkout: str
    documents: str
    database: str
    tasks: str


@dataclass(frozen=True, slots=True)
class Tau3Config:
    """Aggregate the closed configuration schema used by production commands."""

    schema_version: int
    upstream: Tau3UpstreamConfig
    paths: Tau3PathConfig


@dataclass(frozen=True, slots=True)
class ResolvedTau3Paths:
    """Store absolute paths derived from one explicit VerityCX project root."""

    repository_root: Path
    cache_root: Path
    checkout: Path
    documents: Path
    database: Path
    tasks: Path


@dataclass(frozen=True, slots=True)
class DatabaseCollectionShape:
    """Expose only the safe structural shape of one top-level JSON entry."""

    name: str
    json_kind: str
    direct_count: int | None


@dataclass(frozen=True, slots=True)
class GitCheckoutState:
    """Store verified Git identity without worktree filenames or contents."""

    top_level: Path
    origin_url: str
    head_sha: str
    tag_sha: str
    is_clean: bool


@dataclass(frozen=True, slots=True)
class BankingDataState:
    """Store safe aggregate results from required banking-data validation."""

    document_count: int
    task_count: int
    database_collections: tuple[DatabaseCollectionShape, ...]


@dataclass(frozen=True, slots=True)
class SetupResult:
    """Expose the stable non-sensitive result of one setup invocation."""

    status: str
    mode: str
    checkout: str
    tag: str
    commit_sha: str


@dataclass(frozen=True, slots=True)
class InspectionSummary:
    """Expose only approved, immutable banking-data aggregate metadata."""

    tag: str
    commit_sha: str
    document_count: int
    task_count: int
    database_collections: tuple[DatabaseCollectionShape, ...]


def _sanitized_origin_summary(origin: str) -> str:
    """Return a credential-free origin summary without exposing URL parameters.

    Args:
        origin: Untrusted Git remote value read from local repository metadata.

    Returns:
        A useful URL or SSH-style repository locator with credentials removed, or a
        generic marker when the input cannot be represented safely.
    """
    try:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme and parsed.hostname:
            hostname = parsed.hostname
            if ":" in hostname:
                hostname = f"[{hostname}]"
            port = f":{parsed.port}" if parsed.port is not None else ""
            return urllib.parse.urlunsplit(
                (parsed.scheme, f"{hostname}{port}", parsed.path, "", "")
            )
    except ValueError:
        return "<unreportable-origin>"

    # Git also accepts SCP-style remotes such as user@example.invalid:org/repo.git.
    scp_match = re.fullmatch(r"(?:[^@/:]+@)?([^@/:]+):([^\r\n?#]+)", origin)
    if scp_match:
        host, repository_path = scp_match.groups()
        return f"{host}:{repository_path}"
    return "<local-or-unreportable-origin>"


def _configuration_error(message: str, path: Path) -> Tau3OperationError:
    """Create a sanitized configuration failure.

    Args:
        message: Specific closed-schema correction guidance.
        path: Fixed production configuration path.

    Returns:
        Categorized expected error for the CLI boundary.
    """
    return Tau3OperationError("configuration-invalid", message, path)


def _require_mapping(value: object, label: str, config_path: Path) -> dict[str, object]:
    """Validate and copy one untyped TOML mapping into typed boundary state.

    Args:
        value: Untyped value obtained from the TOML parser.
        label: Human-readable schema location.
        config_path: Fixed configuration path used in safe errors.

    Returns:
        Mapping with string keys and object values.

    Raises:
        Tau3OperationError: If the value is not a string-keyed table.
    """
    if not isinstance(value, dict):
        raise _configuration_error(f"{label} must be a TOML table", config_path)
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise _configuration_error(f"{label} contains a non-string key", config_path)
        result[key] = item
    return result


def _require_exact_keys(
    mapping: dict[str, object],
    expected: frozenset[str],
    label: str,
    config_path: Path,
) -> None:
    """Require one closed schema key set without silently accepting drift.

    Args:
        mapping: Validated table to inspect.
        expected: Complete permitted key set.
        label: Human-readable schema location.
        config_path: Fixed configuration path used in safe errors.

    Raises:
        Tau3OperationError: If required keys are missing or unknown keys exist.
    """
    actual = frozenset(mapping)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise _configuration_error(f"{label} is missing {', '.join(missing)}", config_path)
    if unknown:
        raise _configuration_error(
            f"{label} contains unknown keys: {', '.join(unknown)}", config_path
        )


def _require_string(mapping: dict[str, object], key: str, config_path: Path) -> str:
    """Return one required TOML string after boundary validation.

    Args:
        mapping: Validated table containing the key.
        key: Required field name.
        config_path: Fixed configuration path used in safe errors.

    Returns:
        Non-empty string value.

    Raises:
        Tau3OperationError: If the value is missing, empty, or not a string.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise _configuration_error(f"{key} must be a non-empty string", config_path)
    return value


def _validate_relative_path(value: str, field: str, config_path: Path) -> PurePosixPath:
    """Validate portable lexical path syntax before filesystem resolution.

    Args:
        value: Configured forward-slash path.
        field: Configuration field name.
        config_path: Fixed configuration path used in safe errors.

    Returns:
        Validated POSIX-style relative path.

    Raises:
        Tau3OperationError: If the path is absolute, qualified, or escaping.
    """
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        not value
        or "\\" in value
        or posix_path.is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
        or ".." in posix_path.parts
    ):
        raise _configuration_error(f"{field} path must be contained and relative", config_path)
    return posix_path


def load_tau3_config(project_root: Path) -> Tau3Config:
    """Load and validate the fixed production TOML configuration.

    Args:
        project_root: Explicit VerityCX project root containing `config/`.

    Returns:
        Frozen, fully validated production configuration.

    Raises:
        Tau3OperationError: If the file is missing, malformed, open-ended, or unreviewed.
    """
    config_path = project_root.resolve() / _CONFIG_RELATIVE_PATH
    try:
        with config_path.open("rb") as config_file:
            parsed: object = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise _configuration_error(
            f"TOML configuration could not be loaded: {error}", config_path
        ) from None

    root = _require_mapping(parsed, "schema", config_path)
    _require_exact_keys(
        root, frozenset({"schema_version", "upstream", "paths"}), "schema", config_path
    )

    schema_version = root["schema_version"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise _configuration_error("schema_version must be integer 1", config_path)
    if schema_version != 1:
        raise _configuration_error("schema_version must be 1", config_path)

    upstream_raw = _require_mapping(root["upstream"], "upstream", config_path)
    _require_exact_keys(
        upstream_raw,
        frozenset({"repository_url", "license", "tag", "commit_sha"}),
        "upstream",
        config_path,
    )
    repository_url = _require_string(upstream_raw, "repository_url", config_path)
    license_id = _require_string(upstream_raw, "license", config_path)
    tag = _require_string(upstream_raw, "tag", config_path)
    commit_sha = _require_string(upstream_raw, "commit_sha", config_path)
    if not _SHA_PATTERN.fullmatch(commit_sha):
        raise _configuration_error(
            "commit_sha must be 40 lowercase hexadecimal characters", config_path
        )
    expected_upstream = {
        "repository_url": _EXPECTED_REPOSITORY_URL,
        "license": _EXPECTED_LICENSE,
        "tag": _EXPECTED_TAG,
        "commit_sha": _EXPECTED_COMMIT_SHA,
    }
    actual_upstream = {
        "repository_url": repository_url,
        "license": license_id,
        "tag": tag,
        "commit_sha": commit_sha,
    }
    for field, expected_value in expected_upstream.items():
        if actual_upstream[field] != expected_value:
            raise _configuration_error(
                f"{field} does not match the reviewed production value", config_path
            )

    paths_raw = _require_mapping(root["paths"], "paths", config_path)
    _require_exact_keys(paths_raw, frozenset(_EXPECTED_PATHS), "paths", config_path)
    path_values = {
        field: _require_string(paths_raw, field, config_path) for field in _EXPECTED_PATHS
    }
    lexical_paths = {
        field: _validate_relative_path(value, field, config_path)
        for field, value in path_values.items()
    }
    checkout = lexical_paths["checkout"]
    for field in ("documents", "database", "tasks"):
        if not lexical_paths[field].is_relative_to(checkout):
            raise _configuration_error(f"{field} must resolve beneath checkout", config_path)
    for field, expected_value in _EXPECTED_PATHS.items():
        if path_values[field] != expected_value:
            raise _configuration_error(
                f"{field} path does not match the reviewed value", config_path
            )

    return Tau3Config(
        schema_version=schema_version,
        upstream=Tau3UpstreamConfig(repository_url, license_id, tag, commit_sha),
        paths=Tau3PathConfig(**path_values),
    )


def resolve_tau3_paths(project_root: Path, config: Tau3Config) -> ResolvedTau3Paths:
    """Resolve configured paths beneath one explicit project root.

    Args:
        project_root: Explicit trusted VerityCX project root.
        config: Previously validated configuration.

    Returns:
        Absolute contained paths for cache and required banking data.

    Raises:
        Tau3OperationError: If filesystem resolution escapes the project or checkout.
    """
    root = project_root.resolve()
    config_path = root / _CONFIG_RELATIVE_PATH

    def resolve_relative(value: str, field: str) -> Path:
        """Resolve one validated relative path and recheck containment."""
        candidate = (root / Path(PurePosixPath(value))).resolve()
        if not candidate.is_relative_to(root):
            raise _configuration_error(f"{field} resolved path escapes project root", config_path)
        return candidate

    checkout = resolve_relative(config.paths.checkout, "checkout")
    documents = resolve_relative(config.paths.documents, "documents")
    database = resolve_relative(config.paths.database, "database")
    tasks = resolve_relative(config.paths.tasks, "tasks")
    for field, candidate in (("documents", documents), ("database", database), ("tasks", tasks)):
        if not candidate.is_relative_to(checkout):
            raise _configuration_error(f"{field} resolved path escapes checkout", config_path)
    return ResolvedTau3Paths(
        repository_root=root,
        cache_root=root / ".cache",
        checkout=checkout,
        documents=documents,
        database=database,
        tasks=tasks,
    )


def _run_git(
    arguments: Sequence[str],
    *,
    cwd: Path,
    failure_category: str = "git-failed",
) -> str:
    """Run Git through the sanitized non-shell subprocess boundary.

    Args:
        arguments: Git subcommand and arguments, never a shell command string.
        cwd: Explicit working directory for the Git process.
        failure_category: Stable category used for a nonzero process result.

    Returns:
        Trimmed standard output from a successful Git process.

    Raises:
        Tau3OperationError: If Git is unavailable or the process fails.
    """
    git_executable = shutil.which("git")
    if git_executable is None:
        raise Tau3OperationError(
            "git-unavailable",
            "Git 2.34 or newer is required; install Git and retry",
        )
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        # The executable is resolved by shutil.which and arguments bypass a shell.
        result = subprocess.run(  # noqa: S603
            [git_executable, *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            shell=False,
        )
    except OSError:
        raise Tau3OperationError(
            "git-unavailable",
            "Git 2.34 or newer could not be started; repair Git and retry",
        ) from None
    if result.returncode != 0:
        raise Tau3OperationError(
            failure_category,
            f"Git operation failed with exit code {result.returncode}; review local Git state",
            cwd,
        )
    return result.stdout.strip()


def _require_supported_git(cwd: Path) -> None:
    """Require the documented Git baseline without exposing raw version output.

    Args:
        cwd: Safe existing directory for the version process.

    Raises:
        Tau3OperationError: If the installed Git version is malformed or unsupported.
    """
    version_output = _run_git(("--version",), cwd=cwd)
    match = _GIT_VERSION_PATTERN.match(version_output)
    if match is None:
        raise Tau3OperationError(
            "git-unavailable",
            "Git 2.34 or newer is required; the installed version could not be identified",
        )
    version = (int(match.group(1)), int(match.group(2)))
    if version < _MINIMUM_GIT_VERSION:
        raise Tau3OperationError(
            "git-unavailable",
            "Git 2.34 or newer is required; upgrade Git and retry",
        )


def _is_reparse_point(path_stat: os.stat_result) -> bool:
    """Return whether Windows marked a filesystem object as a reparse point.

    Args:
        path_stat: Non-following stat result for the object.

    Returns:
        True for junctions and other Windows reparse points.
    """
    attributes = getattr(path_stat, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _banking_data_error(message: str, path: Path) -> Tau3OperationError:
    """Create a sanitized required-data validation failure.

    Args:
        message: Safe error reason without descendant filenames or contents.
        path: Configured required path, not a traversed descendant.

    Returns:
        Categorized expected banking-data error.
    """
    return Tau3OperationError("banking-data-invalid", message, path)


def _validate_contained_object(path: Path, containment_root: Path, label: str) -> os.stat_result:
    """Validate a real non-link object and its resolved containment.

    Args:
        path: Filesystem object being validated.
        containment_root: Trusted root that must contain the object.
        label: Safe configured field name for diagnostics.

    Returns:
        Non-following stat result for the path.

    Raises:
        Tau3OperationError: If the object is missing, linked, unreadable, or escaping.
    """
    try:
        path_stat = path.lstat()
    except OSError:
        raise _banking_data_error(f"{label} is missing or unreadable", path) from None
    if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
        raise _banking_data_error(f"{label} must not be a link or junction", path)
    try:
        resolved = path.resolve(strict=True)
        resolved_root = containment_root.resolve(strict=True)
    except OSError:
        raise _banking_data_error(f"{label} cannot be resolved safely", path) from None
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise _banking_data_error(f"{label} escapes its configured containment root", path)
    return path_stat


def _open_binary(path: Path) -> BufferedReader:
    """Open one validated regular file for a minimal binary readability check.

    Args:
        path: Real regular file to open.

    Returns:
        Buffered binary reader owned by the caller.
    """
    return path.open("rb")


def _count_readable_files(
    directory: Path,
    containment_root: Path,
    label: str,
    *,
    opener: Callable[[Path], BufferedReader] = _open_binary,
) -> int:
    """Count readable regular descendants without following or exposing names.

    Args:
        directory: Configured directory to traverse recursively.
        containment_root: Trusted checkout containing every descendant.
        label: Safe configured field name for diagnostics.
        opener: Injectable minimal binary-open operation for permission tests.

    Returns:
        Positive recursive readable-file count.

    Raises:
        Tau3OperationError: If traversal encounters unsafe or unreadable state.
    """
    directory_stat = _validate_contained_object(directory, containment_root, label)
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise _banking_data_error(f"{label} must be a directory", directory)
    count = 0
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            raise _banking_data_error(f"{label} directory is unreadable", directory) from None
        for entry in entries:
            descendant = Path(entry.path)
            descendant_stat = _validate_contained_object(descendant, containment_root, label)
            if stat.S_ISDIR(descendant_stat.st_mode):
                pending.append(descendant)
                continue
            if not stat.S_ISREG(descendant_stat.st_mode):
                raise _banking_data_error(f"{label} contains an unsupported object", directory)
            try:
                with opener(descendant) as readable_file:
                    readable_file.read(1)
            except OSError:
                raise _banking_data_error(
                    f"{label} contains an unreadable file", directory
                ) from None
            count += 1
    if count == 0:
        raise _banking_data_error(f"{label} must contain readable regular files", directory)
    return count


def _json_kind(value: object) -> str:
    """Return the stable JSON kind name for one parsed value.

    Args:
        value: Parsed JSON value from a top-level database entry.

    Returns:
        One contract-defined JSON kind.

    Raises:
        Tau3OperationError: If the standard decoder produces an unsupported value.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int | float):
        return "number"
    raise Tau3OperationError("malformed-database", "db.json contains an unsupported JSON value")


def _load_database_shapes(
    database: Path,
    containment_root: Path,
    *,
    opener: Callable[[Path], BufferedReader] = _open_binary,
) -> tuple[DatabaseCollectionShape, ...]:
    """Parse a database into safe top-level shapes without retaining record values.

    Args:
        database: Configured `db.json` path.
        containment_root: Trusted checkout containing the file.
        opener: Injectable binary-open operation for deterministic permission tests.

    Returns:
        Sorted immutable top-level collection shapes.

    Raises:
        Tau3OperationError: If the file is unsafe, unreadable, malformed, or empty.
    """
    database_stat = _validate_contained_object(database, containment_root, "database")
    if not stat.S_ISREG(database_stat.st_mode):
        raise _banking_data_error("database must be a regular file", database)
    try:
        with opener(database) as database_file:
            source = database_file.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise Tau3OperationError(
            "malformed-database",
            "db.json must be a readable UTF-8 JSON file",
            database,
        ) from None
    try:
        parsed: object = json.loads(source)
    except json.JSONDecodeError as error:
        raise Tau3OperationError(
            "malformed-database",
            f"db.json is malformed at line {error.lineno}, column {error.colno}",
            database,
        ) from None
    if not isinstance(parsed, dict) or not parsed:
        raise Tau3OperationError(
            "malformed-database",
            "db.json must contain a non-empty object at the top level",
            database,
        )
    shapes: list[DatabaseCollectionShape] = []
    for name in sorted(parsed):
        if not isinstance(name, str):
            raise Tau3OperationError(
                "malformed-database",
                "db.json contains a non-string top-level name",
                database,
            )
        value: object = parsed[name]
        json_kind = _json_kind(value)
        direct_count = len(value) if isinstance(value, dict | list) else None
        shapes.append(DatabaseCollectionShape(name, json_kind, direct_count))
    return tuple(shapes)


def _checkout_paths(
    project_root: Path,
    config: Tau3Config,
    checkout: Path,
) -> ResolvedTau3Paths:
    """Derive required banking paths for a final or staged checkout.

    Args:
        project_root: Explicit VerityCX project root.
        config: Validated or test-injected configuration.
        checkout: Concrete checkout root being validated.

    Returns:
        Resolved paths whose required data is rooted in the supplied checkout.
    """
    checkout_config = PurePosixPath(config.paths.checkout)

    def under_checkout(configured: str) -> Path:
        """Map one configured checkout descendant beneath the concrete checkout."""
        relative = PurePosixPath(configured).relative_to(checkout_config)
        return checkout.joinpath(*relative.parts)

    return ResolvedTau3Paths(
        repository_root=project_root.resolve(),
        cache_root=(project_root / ".cache").resolve(),
        checkout=checkout.resolve(),
        documents=under_checkout(config.paths.documents),
        database=under_checkout(config.paths.database),
        tasks=under_checkout(config.paths.tasks),
    )


def _path_lstat(path: Path) -> os.stat_result | None:
    """Return a non-following stat result or None only when the path is absent.

    Args:
        path: Path to classify without following links.

    Returns:
        Stat result, or None for a genuinely missing path.

    Raises:
        Tau3OperationError: If classification fails for another reason.
    """
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise Tau3OperationError(
            "unexpected-target",
            "Configured cache state is unreadable; correct permissions and retry",
            path,
        ) from None


def _require_real_directory(path: Path, containment_root: Path, label: str) -> None:
    """Require a readable real directory used for cache or checkout state.

    Args:
        path: Directory to validate without following links.
        containment_root: Project root that must contain the directory.
        label: Safe state name used in diagnostics.

    Raises:
        Tau3OperationError: If the path is unsafe, wrong-kind, unreadable, or escaping.
    """
    path_stat = _path_lstat(path)
    if path_stat is None:
        raise Tau3OperationError(
            "checkout-missing",
            f"{label} is missing; run setup without --check",
            path,
        )
    if (
        not stat.S_ISDIR(path_stat.st_mode)
        or stat.S_ISLNK(path_stat.st_mode)
        or _is_reparse_point(path_stat)
    ):
        raise Tau3OperationError(
            "unexpected-target",
            f"{label} must be a real directory and was preserved; review it manually",
            path,
        )
    try:
        resolved = path.resolve(strict=True)
        root = containment_root.resolve(strict=True)
    except OSError:
        raise Tau3OperationError(
            "unexpected-target",
            f"{label} cannot be resolved safely and was preserved",
            path,
        ) from None
    if resolved != root and not resolved.is_relative_to(root):
        raise Tau3OperationError(
            "unexpected-target",
            f"{label} escapes the project root and was preserved",
            path,
        )
    try:
        with os.scandir(path):
            pass
    except OSError:
        raise Tau3OperationError(
            "unexpected-target",
            f"{label} is unreadable and was preserved; correct permissions manually",
            path,
        ) from None


def _validate_checkout(
    project_root: Path,
    config: Tau3Config,
    paths: ResolvedTau3Paths,
) -> tuple[GitCheckoutState, BankingDataState]:
    """Validate exact Git provenance, cleanliness, and required banking data.

    Args:
        project_root: Explicit VerityCX project root.
        config: Validated or test-injected source identity.
        paths: Concrete final or staging paths to validate.

    Returns:
        Safe immutable Git and banking-data aggregate states.

    Raises:
        Tau3OperationError: If identity, cleanliness, or required data is invalid.
    """
    _require_real_directory(paths.checkout, project_root, "checkout")
    try:
        top_level_text = _run_git(
            ("rev-parse", "--show-toplevel"),
            cwd=paths.checkout,
            failure_category="not-standalone-repository",
        )
    except Tau3OperationError as error:
        if error.category == "not-standalone-repository":
            raise Tau3OperationError(
                error.category,
                "Checkout must be a standalone Git repository; preserve it and review manually",
                paths.checkout,
            ) from None
        raise
    top_level = Path(top_level_text).resolve()
    if top_level != paths.checkout.resolve():
        raise Tau3OperationError(
            "not-standalone-repository",
            "Checkout Git top level differs from the configured root; "
            "preserve it and review manually",
            paths.checkout,
        )

    origin_output = _run_git(
        ("config", "--local", "--get-all", "remote.origin.url"),
        cwd=paths.checkout,
        failure_category="origin-mismatch",
    )
    origins = origin_output.splitlines()
    if origins != [config.upstream.repository_url]:
        detected_summary = (
            _sanitized_origin_summary(origins[0])
            if len(origins) == 1
            else f"{len(origins)} configured origins"
        )
        raise Tau3OperationError(
            "origin-mismatch",
            f"Expected origin {config.upstream.repository_url}; detected {detected_summary}",
            paths.checkout,
        )

    head_sha = _run_git(
        ("rev-parse", "HEAD"),
        cwd=paths.checkout,
        failure_category="revision-mismatch",
    )
    if head_sha != config.upstream.commit_sha:
        raise Tau3OperationError(
            "revision-mismatch",
            f"Expected revision {config.upstream.commit_sha}; detected {head_sha}",
            paths.checkout,
        )
    tag_sha = _run_git(
        ("rev-parse", "--verify", f"refs/tags/{config.upstream.tag}^{{commit}}"),
        cwd=paths.checkout,
        failure_category="tag-mismatch",
    )
    if tag_sha != config.upstream.commit_sha:
        raise Tau3OperationError(
            "tag-mismatch",
            f"Expected tag {config.upstream.tag} at {config.upstream.commit_sha}; binding differs",
            paths.checkout,
        )
    status_output = _run_git(
        ("--no-optional-locks", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=paths.checkout,
        failure_category="dirty-checkout",
    )
    if status_output:
        raise Tau3OperationError(
            "dirty-checkout",
            "Checkout contains local changes; resolve them manually and retry",
            paths.checkout,
        )

    document_count = _count_readable_files(paths.documents, paths.checkout, "documents")
    task_count = _count_readable_files(paths.tasks, paths.checkout, "tasks")
    database_collections = _load_database_shapes(paths.database, paths.checkout)
    return (
        GitCheckoutState(top_level, origins[0], head_sha, tag_sha, True),
        BankingDataState(document_count, task_count, database_collections),
    )


def _setup_result(config: Tau3Config, mode: str) -> SetupResult:
    """Build the stable public setup result for one successful mode.

    Args:
        config: Verified source and path configuration.
        mode: One of installed, existing, or check.

    Returns:
        Non-sensitive immutable setup result.
    """
    return SetupResult(
        status="valid",
        mode=mode,
        checkout=config.paths.checkout,
        tag=config.upstream.tag,
        commit_sha=config.upstream.commit_sha,
    )


def _remove_owned_state(staging_parent: Path | None, lock: Path, owns_lock: bool) -> None:
    """Remove only staging and lock paths proven to belong to this invocation.

    Args:
        staging_parent: Unique parent created by this invocation, if any.
        lock: Cooperative lock path.
        owns_lock: Whether this invocation successfully created the lock.

    Raises:
        Tau3OperationError: If owned state cannot be removed completely.
    """

    def clear_readonly_and_retry(
        function: Callable[[str], object],
        path: str,
        _error: BaseException,
    ) -> None:
        """Clear Git's Windows read-only bit only inside current-run-owned staging."""
        Path(path).chmod(stat.S_IREAD | stat.S_IWRITE)
        function(path)

    try:
        if staging_parent is not None and _path_lstat(staging_parent) is not None:
            shutil.rmtree(staging_parent, onexc=clear_readonly_and_retry)
        if owns_lock and _path_lstat(lock) is not None:
            lock.rmdir()
    except OSError:
        retained = staging_parent if staging_parent is not None else lock
        raise Tau3OperationError(
            "staging-cleanup-failed",
            "Current-run setup state could not be removed; review the reported path manually",
            retained,
        ) from None


def setup_tau3_data(
    project_root: Path,
    *,
    config: Tau3Config | None = None,
    check_only: bool = False,
) -> SetupResult:
    """Acquire or validate the pinned tau3 checkout without altering existing state.

    Args:
        project_root: Explicit VerityCX project root.
        config: Optional typed test injection; production loads the fixed TOML file.
        check_only: Perform validation only and create no cache, lock, or staging state.

    Returns:
        Stable setup result for installed, existing, or check mode.

    Raises:
        Tau3OperationError: For every expected configuration, Git, data, or transaction failure.
    """
    root = project_root.resolve()
    effective_config = config if config is not None else load_tau3_config(root)
    paths = resolve_tau3_paths(root, effective_config)
    target_state = _path_lstat(paths.checkout)
    if target_state is not None:
        _require_supported_git(root)
        _validate_checkout(root, effective_config, paths)
        return _setup_result(effective_config, "check" if check_only else "existing")
    if check_only:
        raise Tau3OperationError(
            "checkout-missing",
            "Checkout is missing; run setup without --check",
            paths.checkout,
        )

    _require_supported_git(root)
    cache_state = _path_lstat(paths.cache_root)
    if cache_state is None:
        try:
            paths.cache_root.mkdir()
        except FileExistsError:
            pass
        except OSError:
            raise Tau3OperationError(
                "unexpected-target",
                "Cache root could not be created safely; review project permissions",
                paths.cache_root,
            ) from None
    _require_real_directory(paths.cache_root, root, "cache root")

    lock = paths.cache_root / "tau3-bench.setup.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise Tau3OperationError(
            "setup-locked",
            "Setup lock already exists; review its owner and recover manually",
            lock,
        ) from None
    except OSError:
        raise Tau3OperationError(
            "setup-locked",
            "Setup lock could not be claimed; review cache permissions",
            lock,
        ) from None

    owns_lock = True
    staging_parent: Path | None = None
    promoted = False
    try:
        if _path_lstat(paths.checkout) is not None:
            raise Tau3OperationError(
                "destination-conflict",
                "Checkout appeared after lock acquisition and was preserved",
                paths.checkout,
            )
        staging_parent = Path(
            tempfile.mkdtemp(prefix="tau3-bench-staging-", dir=paths.cache_root),
        )
        staging_checkout = staging_parent / "checkout"
        _run_git(
            (
                "clone",
                "--no-local",
                "--branch",
                effective_config.upstream.tag,
                "--single-branch",
                "--",
                effective_config.upstream.repository_url,
                str(staging_checkout),
            ),
            cwd=root,
            failure_category="clone-failed",
        )
        staging_paths = _checkout_paths(root, effective_config, staging_checkout)
        _validate_checkout(root, effective_config, staging_paths)
        _run_git(
            ("--no-optional-locks", "status", "--porcelain=v1", "--untracked-files=all"),
            cwd=staging_checkout,
            failure_category="dirty-checkout",
        )
        if _path_lstat(paths.checkout) is not None:
            raise Tau3OperationError(
                "destination-conflict",
                "Checkout appeared before promotion and was preserved",
                paths.checkout,
            )
        try:
            staging_checkout.rename(paths.checkout)
        except FileExistsError:
            raise Tau3OperationError(
                "destination-conflict",
                "Checkout appeared during promotion and was preserved",
                paths.checkout,
            ) from None
        except OSError:
            raise Tau3OperationError(
                "destination-conflict",
                "Non-replacing checkout promotion failed; inspect destination state manually",
                paths.checkout,
            ) from None
        promoted = True
        _validate_checkout(root, effective_config, paths)
        return _setup_result(effective_config, "installed")
    finally:
        # Once promoted, cleanup never targets the final checkout; only the empty staging parent.
        _remove_owned_state(staging_parent, lock, owns_lock)
        if promoted:
            owns_lock = False


def inspect_tau3_data(
    project_root: Path,
    *,
    config: Tau3Config | None = None,
) -> InspectionSummary:
    """Validate twice and return a buffered, non-sensitive banking summary.

    Args:
        project_root: Explicit VerityCX project root.
        config: Optional typed test injection; production loads the fixed TOML file.

    Returns:
        Immutable aggregate metadata after two matching validation observations.

    Raises:
        Tau3OperationError: If checkout validation fails or observations differ.
    """
    root = project_root.resolve()
    effective_config = config if config is not None else load_tau3_config(root)
    paths = resolve_tau3_paths(root, effective_config)
    if _path_lstat(paths.checkout) is None:
        raise Tau3OperationError(
            "checkout-missing",
            "Checkout is missing; run setup before inspection",
            paths.checkout,
        )
    _require_supported_git(root)
    initial_git, initial_data = _validate_checkout(root, effective_config, paths)
    final_git, final_data = _validate_checkout(root, effective_config, paths)
    if initial_git != final_git or initial_data != final_data:
        raise Tau3OperationError(
            "checkout-changed",
            "Checkout changed during inspection; retry after concurrent activity stops",
            paths.checkout,
        )
    return InspectionSummary(
        tag=effective_config.upstream.tag,
        commit_sha=final_git.head_sha,
        document_count=final_data.document_count,
        task_count=final_data.task_count,
        database_collections=final_data.database_collections,
    )
