"""Test reproducible and non-disclosing tau3-Banking data operations."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, asdict, dataclass
from io import BufferedReader
from pathlib import Path
from types import ModuleType

import pytest

from veritycx.data_sources.tau3 import (
    BankingDataState,
    DatabaseCollectionShape,
    GitCheckoutState,
    ResolvedTau3Paths,
    Tau3Config,
    Tau3OperationError,
    Tau3PathConfig,
    Tau3UpstreamConfig,
)

REPOSITORY_URL = "https://github.com/sierra-research/tau2-bench.git"
TAG = "v1.0.1"
COMMIT_SHA = "fc0055dc4e0a316c3f83133267fbd6faaa770992"
DOCUMENT_CANARY = "DOCUMENT_BODY_CANARY"
RECORD_CANARY = "CUSTOMER_RECORD_CANARY"
TASK_CANARY = "TASK_PROMPT_CANARY"
ANSWER_CANARY = "EXPECTED_ANSWER_CANARY"
REFERENCE_CANARY = "REFERENCE_ACTION_CANARY"
GRADING_CANARY = "GRADING_CRITERIA_CANARY"


@dataclass(frozen=True, slots=True)
class LocalTau3Fixture:
    """Describe one synthetic local repository and its injected configuration."""

    project_root: Path
    source_repository: Path
    bare_remote: Path
    config: Tau3Config
    commit_sha: str


@dataclass(frozen=True, slots=True)
class TreeSnapshot:
    """Capture byte, kind, mode, and link identity without access timestamps."""

    entries: tuple[tuple[str, str, int, str], ...]


def _tau3_module() -> ModuleType:
    """Import the implementation lazily so missing behavior fails inside tests."""
    return importlib.import_module("veritycx.data_sources.tau3")


def _setup_script_module() -> ModuleType:
    """Load the project-root setup script without changing Python import paths."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "setup_tau3_data.py"
    specification = importlib.util.spec_from_file_location(
        "veritycx_test_setup_script", script_path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("setup script could not be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _inspection_script_module() -> ModuleType:
    """Load the project-root inspection script without changing import paths."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "inspect_tau3_banking_data.py"
    specification = importlib.util.spec_from_file_location(
        "veritycx_test_inspection_script", script_path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("inspection script could not be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _production_toml(*, checkout: str = ".cache/tau3-bench/") -> str:
    """Return a complete production-schema TOML document for boundary tests."""
    return f'''# Test-only production-schema configuration.
schema_version = 1

[upstream]
repository_url = "{REPOSITORY_URL}"
license = "MIT"
tag = "{TAG}"
commit_sha = "{COMMIT_SHA}"

[paths]
checkout = "{checkout}"
documents = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/"
database = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json"
tasks = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/"
'''


def _write_config(project_root: Path, content: str) -> Path:
    """Write test configuration beneath an isolated project root."""
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "tau3-bench.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


@contextmanager
def _changed_directory(path: Path) -> Iterator[None]:
    """Temporarily change directory to prove explicit-root behavior."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run deterministic local Git setup commands for later fixture tests."""
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("Git is required for the local fixture")
    # The test harness fixes the executable to resolved Git and never invokes a shell.
    return subprocess.run(  # noqa: S603
        [git_executable, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _create_local_fixture(
    tmp_path: Path,
    *,
    variant: str | None = None,
) -> LocalTau3Fixture:
    """Create a tagged local Git remote with runtime-generated banking canaries."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_repository = tmp_path / "source"
    source_repository.mkdir()
    banking_root = source_repository / "data" / "tau2" / "domains" / "banking_knowledge"
    documents = banking_root / "documents"
    tasks = banking_root / "tasks"
    documents.mkdir(parents=True)
    tasks.mkdir()
    (documents / "guide.md").write_text(DOCUMENT_CANARY, encoding="utf-8")
    (banking_root / "db.json").write_text(
        json.dumps(
            {
                "accounts": {"record": RECORD_CANARY},
                "active": True,
                "description": "DATABASE_SCALAR_CANARY",
                "empty": None,
                "flags": [],
                "version": 1,
            },
        ),
        encoding="utf-8",
    )
    (tasks / "task.json").write_text(
        json.dumps(
            {
                "prompt": TASK_CANARY,
                "expected_answer": ANSWER_CANARY,
                "reference_action": REFERENCE_CANARY,
                "grading": GRADING_CANARY,
            },
        ),
        encoding="utf-8",
    )
    if variant == "missing-database":
        (banking_root / "db.json").unlink()
    elif variant == "malformed-database":
        (banking_root / "db.json").write_text("{MALFORMED_DATABASE_CANARY", encoding="utf-8")
    elif variant == "empty-database-object":
        (banking_root / "db.json").write_text("{}", encoding="utf-8")
    elif variant == "nonstandard-database":
        (banking_root / "db.json").write_text(
            '{"accounts": NaN, "private": "DATABASE_SOURCE_CANARY"}',
            encoding="utf-8",
        )
    elif variant == "documents-file":
        shutil.rmtree(documents)
        documents.write_text("wrong kind", encoding="utf-8")
    elif variant == "tasks-missing":
        shutil.rmtree(tasks)
    elif variant is not None:
        raise ValueError(f"unknown fixture variant: {variant}")
    _run_git("init", "--initial-branch", "main", cwd=source_repository)
    _run_git("config", "user.name", "VerityCX Test", cwd=source_repository)
    _run_git("config", "user.email", "veritycx-test@example.invalid", cwd=source_repository)
    _run_git("add", ".", cwd=source_repository)
    _run_git("commit", "-m", "Create synthetic tau3 fixture", cwd=source_repository)
    _run_git("tag", TAG, cwd=source_repository)
    commit_sha = _run_git("rev-parse", "HEAD", cwd=source_repository).stdout.strip()
    bare_remote = tmp_path / "remote.git"
    _run_git("clone", "--bare", str(source_repository), str(bare_remote), cwd=tmp_path)
    config = Tau3Config(
        schema_version=1,
        upstream=Tau3UpstreamConfig(
            repository_url=bare_remote.as_uri(),
            license_id="MIT",
            tag=TAG,
            commit_sha=commit_sha,
        ),
        paths=Tau3PathConfig(
            checkout=".cache/tau3-bench/",
            documents=(".cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/"),
            database=".cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json",
            tasks=".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/",
        ),
    )
    return LocalTau3Fixture(
        project_root=project_root,
        source_repository=source_repository,
        bare_remote=bare_remote,
        config=config,
        commit_sha=commit_sha,
    )


def _snapshot_tree(root: Path) -> TreeSnapshot:
    """Snapshot a tree without following links or recording access timestamps."""
    if not root.exists():
        return TreeSnapshot(())
    entries: list[tuple[str, str, int, str]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        for entry in os.scandir(current):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            path_stat = entry.stat(follow_symlinks=False)
            mode = path_stat.st_mode
            if entry.is_symlink():
                entries.append((relative, "link", mode, os.readlink(path)))
            elif entry.is_dir(follow_symlinks=False):
                entries.append((relative, "directory", mode, ""))
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append((relative, "file", mode, digest))
            else:
                entries.append((relative, "special", mode, ""))
    return TreeSnapshot(tuple(sorted(entries)))


def test_load_config_accepts_the_exact_closed_schema(tmp_path: Path) -> None:
    """Load the reviewed production values into immutable typed objects."""
    _write_config(tmp_path, _production_toml())

    config = _tau3_module().load_tau3_config(tmp_path)

    assert config.schema_version == 1
    assert config.upstream.repository_url == REPOSITORY_URL
    assert config.upstream.tag == TAG
    assert config.upstream.commit_sha == COMMIT_SHA
    assert config.paths.checkout == ".cache/tau3-bench/"


@pytest.mark.parametrize(
    ("content", "expected_fragment"),
    [
        ("", "schema"),
        (_production_toml().replace("schema_version = 1\n", ""), "schema_version"),
        (_production_toml() + "\nunknown = true\n", "unknown"),
        (
            _production_toml().replace(
                'license = "MIT"',
                'license = "MIT"\nunknown_upstream = true',
            ),
            "unknown",
        ),
        (
            _production_toml().replace(
                'tasks = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/"',
                'tasks = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/"\n'
                'unknown_path = ".cache/other/"',
            ),
            "unknown",
        ),
        (_production_toml().replace(f'tag = "{TAG}"\n', ""), "tag"),
        (_production_toml().replace("schema_version = 1", "schema_version = true"), "integer"),
        (_production_toml().replace(f'tag = "{TAG}"', "tag = true"), "string"),
        (_production_toml().replace('license = "MIT"', 'license = "Apache-2.0"'), "license"),
        (_production_toml().replace(COMMIT_SHA, "abc"), "commit_sha"),
        (
            _production_toml().replace(
                "\n[upstream]",
                "\nschema_version = 1\n\n[upstream]",
            ),
            "TOML",
        ),
    ],
)
def test_load_config_rejects_malformed_or_nonproduction_values(
    tmp_path: Path,
    content: str,
    expected_fragment: str,
) -> None:
    """Reject malformed, open-ended, wrongly typed, or unreviewed configuration."""
    _write_config(tmp_path, content)

    with pytest.raises(Exception, match=expected_fragment):
        _tau3_module().load_tau3_config(tmp_path)


@pytest.mark.parametrize(
    "checkout",
    [
        "/absolute/tau3-bench",
        "C:/absolute/tau3-bench",
        "//server/share/tau3-bench",
        ".cache/../escape",
        "../outside",
    ],
)
def test_resolve_paths_rejects_absolute_drive_unc_and_parent_paths(
    tmp_path: Path,
    checkout: str,
) -> None:
    """Reject configured paths that are absolute, qualified, or traversing."""
    _write_config(tmp_path, _production_toml(checkout=checkout))

    with pytest.raises(Exception, match="path"):
        _tau3_module().load_tau3_config(tmp_path)


def test_resolve_paths_rejects_required_paths_outside_checkout(tmp_path: Path) -> None:
    """Require all banking paths to be strict descendants of the checkout."""
    content = _production_toml().replace(
        ".cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/",
        ".cache/other/documents/",
    )
    _write_config(tmp_path, content)

    with pytest.raises(Exception, match="checkout"):
        _tau3_module().load_tau3_config(tmp_path)


@pytest.mark.parametrize("escaping_field", ["checkout", "documents", "database", "tasks"])
def test_resolve_paths_rejects_filesystem_resolved_escapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    escaping_field: str,
) -> None:
    """Recheck containment after filesystem resolution for every configured path."""
    project_root = tmp_path / "project"
    outside = tmp_path / "outside"
    project_root.mkdir()
    outside.mkdir()
    config = Tau3Config(
        1,
        Tau3UpstreamConfig(REPOSITORY_URL, "MIT", TAG, COMMIT_SHA),
        Tau3PathConfig(
            checkout=".cache/tau3-bench/",
            documents=".cache/tau3-bench/data/documents/",
            database=".cache/tau3-bench/data/db.json",
            tasks=".cache/tau3-bench/data/tasks/",
        ),
    )
    configured = {
        "checkout": project_root / config.paths.checkout,
        "documents": project_root / config.paths.documents,
        "database": project_root / config.paths.database,
        "tasks": project_root / config.paths.tasks,
    }
    original_resolve = Path.resolve

    def resolve_with_escape(path: Path, strict: bool = False) -> Path:
        """Resolve exactly one configured path outside its required containment."""
        if path == configured[escaping_field]:
            if escaping_field == "checkout":
                return outside
            return project_root / "other" / path.name
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_with_escape)

    with pytest.raises(Tau3OperationError, match="escapes"):
        _tau3_module().resolve_tau3_paths(project_root, config)


def test_config_and_paths_are_independent_of_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve every path from the explicit project root, never process cwd."""
    project_root = tmp_path / "project"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _write_config(project_root, _production_toml())
    module = _tau3_module()

    with _changed_directory(elsewhere):
        config = module.load_tau3_config(project_root)
        resolved = module.resolve_tau3_paths(project_root, config)

    assert resolved.repository_root == project_root.resolve()
    assert resolved.checkout == (project_root / ".cache" / "tau3-bench").resolve()
    monkeypatch.chdir(project_root)


def test_git_runner_uses_argument_list_and_read_only_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invoke Git without a shell or inherited repository and config controls."""
    module = _tau3_module()
    observed: dict[str, object] = {}
    poisoned_environment = {
        "GIT_DIR": str(tmp_path / "foreign.git"),
        "GIT_WORK_TREE": str(tmp_path / "foreign-worktree"),
        "GIT_INDEX_FILE": str(tmp_path / "foreign.index"),
        "GIT_OBJECT_DIRECTORY": str(tmp_path / "foreign-objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(tmp_path / "alternate-objects"),
        "GIT_COMMON_DIR": str(tmp_path / "foreign-common"),
        "GIT_NAMESPACE": "foreign-namespace",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "hostile-global-config"),
        "GIT_CONFIG_SYSTEM": str(tmp_path / "hostile-system-config"),
        "GIT_CONFIG_PARAMETERS": "'url.https://hostile.invalid/.insteadOf'='https://'",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "hostile-helper",
        "GIT_CONFIG_KEY_1": "url.https://hostile.invalid/.insteadOf",
        "GIT_CONFIG_VALUE_1": "https://",
        "GIT_SSH": str(tmp_path / "hostile-ssh"),
        "GIT_SSH_COMMAND": "hostile-ssh-command",
        "GIT_ASKPASS": str(tmp_path / "hostile-git-askpass"),
        "SSH_ASKPASS": str(tmp_path / "hostile-ssh-askpass"),
        "SSH_ASKPASS_REQUIRE": "force",
    }
    for name, value in poisoned_environment.items():
        monkeypatch.setenv(name, value)

    def fake_which(executable: str) -> str:
        """Return a deterministic resolved Git executable."""
        assert executable == "git"
        return "C:/Git/bin/git.exe"

    def fake_run(
        arguments: Sequence[str],
        **options: object,
    ) -> subprocess.CompletedProcess[str]:
        """Capture the subprocess boundary without executing Git."""
        observed["arguments"] = list(arguments)
        observed.update(options)
        return subprocess.CompletedProcess(arguments, 0, stdout="clean\n", stderr="")

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    output = module._run_git(
        ("status", "--porcelain=v1"),
        cwd=tmp_path,
        failure_category="dirty-checkout",
    )

    assert output == "clean"
    assert observed["arguments"] == ["C:/Git/bin/git.exe", "status", "--porcelain=v1"]
    assert observed["shell"] is False
    assert observed["check"] is False
    environment = observed["env"]
    assert isinstance(environment, dict)
    git_controls = {
        name: value
        for name, value in environment.items()
        if name.startswith("GIT_") or name.startswith("SSH_ASKPASS")
    }
    assert git_controls == {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_KEY_1": "core.askPass",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_VALUE_1": "",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }


def test_git_runner_ignores_inherited_repository_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve Git state from the explicit cwd despite hostile parent controls."""
    module = _tau3_module()
    intended_repository = tmp_path / "intended"
    foreign_repository = tmp_path / "foreign"
    intended_repository.mkdir()
    foreign_repository.mkdir()
    _run_git("init", "--initial-branch", "main", cwd=intended_repository)
    _run_git("init", "--initial-branch", "main", cwd=foreign_repository)
    monkeypatch.setenv("GIT_DIR", str(foreign_repository / ".git"))

    git_directory = module._run_git(
        ("rev-parse", "--git-dir"),
        cwd=intended_repository,
        failure_category="not-standalone-repository",
    )

    assert Path(git_directory) == Path(".git")


def test_git_runner_reports_missing_git_without_traceback_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Translate an absent Git executable into the stable prerequisite category."""
    module = _tau3_module()
    monkeypatch.setattr(module.shutil, "which", lambda _executable: None)

    with pytest.raises(Tau3OperationError, match=r"Git 2\.34") as raised:
        module._run_git(("status",), cwd=tmp_path, failure_category="dirty-checkout")

    assert raised.value.category == "git-unavailable"


def test_git_runner_sanitizes_nonzero_process_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exclude raw Git stderr and command arguments from expected failures."""
    module = _tau3_module()
    canary = "SECRET_GIT_OUTPUT_CANARY"
    monkeypatch.setattr(module.shutil, "which", lambda _executable: "C:/Git/bin/git.exe")

    def fake_run(
        arguments: Sequence[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[str]:
        """Return a deterministic failing Git process."""
        return subprocess.CompletedProcess(arguments, 128, stdout="", stderr=canary)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(Tau3OperationError) as raised:
        module._run_git(("status", canary), cwd=tmp_path, failure_category="clone-failed")

    assert raised.value.category == "clone-failed"
    assert raised.value.message == (
        "Git operation failed with exit code 128; detail=unreportable Git error"
    )
    assert canary not in str(raised.value)


def test_git_version_process_failure_uses_declared_prerequisite_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Map a failed Git version probe to the public prerequisite diagnostic."""
    module = _tau3_module()
    monkeypatch.setattr(module.shutil, "which", lambda _executable: "C:/Git/bin/git.exe")

    def failed_version(
        arguments: Sequence[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[str]:
        """Return a deterministic version-process failure."""
        return subprocess.CompletedProcess(arguments, 1, stdout="", stderr="failure")

    monkeypatch.setattr(module.subprocess, "run", failed_version)

    with pytest.raises(Tau3OperationError) as raised:
        module._require_supported_git(tmp_path)

    assert raised.value.category == "git-unavailable"


def test_operation_error_rejects_undeclared_diagnostic_categories() -> None:
    """Prevent an internal category from reaching either public CLI renderer."""
    with pytest.raises(ValueError, match="declared"):
        Tau3OperationError("git-failed", "internal category")


def test_git_boundary_rejects_an_unsupported_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Require the documented Git 2.34 minimum before acquisition."""
    module = _tau3_module()

    def old_git(
        _arguments: Sequence[str],
        *,
        cwd: Path,
        failure_category: str,
    ) -> str:
        """Return an installed but unsupported Git version."""
        assert cwd == tmp_path
        assert failure_category == "git-unavailable"
        return "git version 2.33.9"

    monkeypatch.setattr(module, "_run_git", old_git, raising=False)

    with pytest.raises(Tau3OperationError, match=r"2\.34") as raised:
        module._require_supported_git(tmp_path)

    assert raised.value.category == "git-unavailable"


def test_file_counter_counts_nested_readable_regular_files(tmp_path: Path) -> None:
    """Count contained regular descendants without decoding their contents."""
    checkout = tmp_path / "checkout"
    documents = checkout / "documents"
    nested = documents / "nested"
    nested.mkdir(parents=True)
    (documents / "one.md").write_bytes(b"one")
    (nested / "two.md").write_bytes(b"two")

    count = _tau3_module()._count_readable_files(documents, checkout, "documents")

    assert count == 2


def test_file_counter_rejects_symbolic_links_without_following(
    tmp_path: Path,
) -> None:
    """Reject a linked descendant before any target content is opened."""
    checkout = tmp_path / "checkout"
    documents = checkout / "documents"
    outside = tmp_path / "outside.txt"
    documents.mkdir(parents=True)
    outside.write_text("LINK_TARGET_CANARY", encoding="utf-8")
    link = documents / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symbolic links unavailable: {error}")

    with pytest.raises(Exception, match="link"):
        _tau3_module()._count_readable_files(documents, checkout, "documents")


def test_file_counter_reports_injected_permission_failure(tmp_path: Path) -> None:
    """Treat a deterministic minimal-open permission failure as unreadable."""
    checkout = tmp_path / "checkout"
    documents = checkout / "documents"
    documents.mkdir(parents=True)
    (documents / "blocked.md").write_bytes(b"blocked")

    def deny_open(_path: Path) -> BufferedReader:
        """Raise the cross-platform permission result under test."""
        raise PermissionError("injected")

    with pytest.raises(Exception, match="unreadable"):
        _tau3_module()._count_readable_files(
            documents,
            checkout,
            "documents",
            opener=deny_open,
        )


@pytest.mark.parametrize("label", ["documents", "tasks"])
@pytest.mark.parametrize(
    "variant",
    ["missing", "empty", "wrong-kind", "unreadable", "link", "junction", "special", "escape"],
)
def test_required_directory_validation_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    variant: str,
) -> None:
    """Reject every unsafe required-directory state with its configured path."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    required = checkout / label
    outside = tmp_path / "outside"
    outside.mkdir()
    module = _tau3_module()
    opener: Callable[[Path], BufferedReader] = module._open_binary
    if variant == "wrong-kind":
        required.write_text("WRONG_KIND_CONTENT_CANARY", encoding="utf-8")
    elif variant != "missing":
        required.mkdir()
        if variant == "unreadable":
            (required / "blocked.bin").write_bytes(b"BLOCKED_CONTENT_CANARY")

            def deny_open(_path: Path) -> BufferedReader:
                """Inject a deterministic unreadable descendant."""
                raise PermissionError("injected")

            opener = deny_open
        elif variant not in {"empty", "link", "junction", "special", "escape"}:
            (required / "valid.bin").write_bytes(b"valid")
    if variant == "link":
        original_lstat: Callable[[Path], os.stat_result] = Path.lstat
        linked_stat = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def lstat_link(path: Path) -> os.stat_result:
            """Classify only the configured path as a symbolic link."""
            if path == required:
                return linked_stat
            return original_lstat(path)

        monkeypatch.setattr(Path, "lstat", lstat_link)
    elif variant == "junction":
        monkeypatch.setattr(module, "_is_reparse_point", lambda _path_stat: True)
    elif variant == "special":
        original_validate: Callable[[Path, Path, str], os.stat_result] = (
            module._validate_contained_object
        )
        special_stat = os.stat_result((stat.S_IFIFO | 0o600, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def validate_special(path: Path, root: Path, safe_label: str) -> os.stat_result:
            """Classify only the configured path as a special filesystem object."""
            if path == required:
                return special_stat
            return original_validate(path, root, safe_label)

        monkeypatch.setattr(module, "_validate_contained_object", validate_special)
    elif variant == "escape":
        original_resolve = Path.resolve

        def resolve_escape(path: Path, strict: bool = False) -> Path:
            """Resolve only the configured path outside its checkout."""
            if path == required:
                return outside
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", resolve_escape)

    with pytest.raises(Tau3OperationError) as raised:
        module._count_readable_files(required, checkout, label, opener=opener)

    assert raised.value.category == "banking-data-invalid"
    assert raised.value.path == required
    assert "CONTENT_CANARY" not in str(raised.value)


def test_database_shapes_include_only_top_level_safe_metadata(tmp_path: Path) -> None:
    """Derive sorted kinds and direct collection counts without nested values."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    database = checkout / "db.json"
    database.write_text(
        '{"z": null, "records": {"SECRET_RECORD_ID": {"value": "CANARY"}}, '
        '"items": [], "enabled": true, "name": "bank", "rate": 1.5}',
        encoding="utf-8",
    )

    shapes = _tau3_module()._load_database_shapes(database, checkout)

    assert [(shape.name, shape.json_kind, shape.direct_count) for shape in shapes] == [
        ("enabled", "boolean", None),
        ("items", "array", 0),
        ("name", "string", None),
        ("rate", "number", None),
        ("records", "object", 1),
        ("z", "null", None),
    ]
    assert "SECRET_RECORD_ID" not in repr(shapes)
    assert "CANARY" not in repr(shapes)


@pytest.mark.parametrize(
    "content",
    ["", "{broken", "[]", "null", "{}"],
)
def test_database_shapes_reject_invalid_roots_without_source_echo(
    tmp_path: Path,
    content: str,
) -> None:
    """Reject invalid database syntax or roots without returning source text."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    database = checkout / "db.json"
    canary = "DATABASE_SOURCE_CANARY"
    database.write_text(content + canary, encoding="utf-8")

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module()._load_database_shapes(database, checkout)

    assert raised.value.category == "malformed-database"
    assert canary not in str(raised.value)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_database_shapes_reject_nonstandard_numeric_constants(
    tmp_path: Path,
    constant: str,
) -> None:
    """Reject JavaScript numeric extensions without echoing database source."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    database = checkout / "db.json"
    canary = "NONSTANDARD_DATABASE_SOURCE_CANARY"
    database.write_text(
        f'{{"accounts": {constant}, "private": "{canary}"}}',
        encoding="utf-8",
    )

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module()._load_database_shapes(database, checkout)

    assert raised.value.category == "malformed-database"
    assert canary not in str(raised.value)


@pytest.mark.parametrize(
    "variant",
    ["missing", "empty", "wrong-kind", "unreadable", "link", "junction", "special", "escape"],
)
def test_required_database_validation_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    """Reject every unsafe database state with only its configured path."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    database = checkout / "db.json"
    outside = tmp_path / "outside.json"
    outside.write_text('{"outside": true}', encoding="utf-8")
    module = _tau3_module()
    opener: Callable[[Path], BufferedReader] = module._open_binary
    if variant == "wrong-kind":
        database.mkdir()
    elif variant != "missing":
        database.write_text("" if variant == "empty" else '{"valid": true}', encoding="utf-8")
    if variant == "unreadable":

        def deny_open(_path: Path) -> BufferedReader:
            """Inject a deterministic unreadable database file."""
            raise PermissionError("injected")

        opener = deny_open
    elif variant == "link":
        original_lstat: Callable[[Path], os.stat_result] = Path.lstat
        linked_stat = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def lstat_link(path: Path) -> os.stat_result:
            """Classify only the configured database as a symbolic link."""
            if path == database:
                return linked_stat
            return original_lstat(path)

        monkeypatch.setattr(Path, "lstat", lstat_link)
    elif variant == "junction":
        monkeypatch.setattr(module, "_is_reparse_point", lambda _path_stat: True)
    elif variant == "special":
        original_validate: Callable[[Path, Path, str], os.stat_result] = (
            module._validate_contained_object
        )
        special_stat = os.stat_result((stat.S_IFIFO | 0o600, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def validate_special(path: Path, root: Path, label: str) -> os.stat_result:
            """Classify only the configured database as a special object."""
            if path == database:
                return special_stat
            return original_validate(path, root, label)

        monkeypatch.setattr(module, "_validate_contained_object", validate_special)
    elif variant == "escape":
        original_resolve = Path.resolve

        def resolve_escape(path: Path, strict: bool = False) -> Path:
            """Resolve only the configured database outside its checkout."""
            if path == database:
                return outside
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", resolve_escape)

    with pytest.raises(Tau3OperationError) as raised:
        module._load_database_shapes(database, checkout, opener=opener)

    assert raised.value.category in {"banking-data-invalid", "malformed-database"}
    assert raised.value.path == database
    assert "outside" not in str(raised.value)


def test_inspection_rejects_nonstandard_database_constants_without_output(
    tmp_path: Path,
) -> None:
    """Apply strict JSON validation through the complete inspection boundary."""
    fixture = _create_local_fixture(tmp_path, variant="nonstandard-database")
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    checkout.parent.mkdir()
    _run_git(
        "clone",
        "--branch",
        TAG,
        "--single-branch",
        "--",
        fixture.config.upstream.repository_url,
        str(checkout),
        cwd=fixture.project_root,
    )
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().inspect_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "malformed-database"
    assert "DATABASE_SOURCE_CANARY" not in str(raised.value)
    assert _snapshot_tree(checkout) == before


def test_first_install_promotes_only_a_fully_validated_checkout(tmp_path: Path) -> None:
    """Acquire the local fixture through staging and prove exact Git/data identity."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()

    result = module.setup_tau3_data(fixture.project_root, config=fixture.config)

    checkout = fixture.project_root / ".cache" / "tau3-bench"
    assert result.status == "valid"
    assert result.mode == "installed"
    assert result.tag == TAG
    assert result.commit_sha == fixture.commit_sha
    assert checkout.is_dir()
    assert _run_git(
        "config", "--local", "--get", "remote.origin.url", cwd=checkout
    ).stdout.strip() == (fixture.config.upstream.repository_url)
    assert _run_git("rev-parse", "HEAD", cwd=checkout).stdout.strip() == fixture.commit_sha
    assert _run_git(
        "rev-parse", "--verify", f"refs/tags/{TAG}^{{commit}}", cwd=checkout
    ).stdout.strip() == (fixture.commit_sha)
    assert _run_git("status", "--porcelain=v1", "--untracked-files=all", cwd=checkout).stdout == ""
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


def test_inspection_summary_is_complete_immutable_and_non_disclosing(tmp_path: Path) -> None:
    """Return only approved aggregate metadata across every JSON kind."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)

    summary = module.inspect_tau3_data(fixture.project_root, config=fixture.config)

    assert summary.tag == TAG
    assert summary.commit_sha == fixture.commit_sha
    assert summary.document_count == 1
    assert summary.task_count == 1
    assert [
        (shape.name, shape.json_kind, shape.direct_count) for shape in summary.database_collections
    ] == [
        ("accounts", "object", 1),
        ("active", "boolean", None),
        ("description", "string", None),
        ("empty", "null", None),
        ("flags", "array", 0),
        ("version", "number", None),
    ]
    with pytest.raises(FrozenInstanceError):
        summary.tag = "changed"
    exposed = repr(summary) + json.dumps(asdict(summary), sort_keys=True)
    for canary in (
        DOCUMENT_CANARY,
        RECORD_CANARY,
        TASK_CANARY,
        ANSWER_CANARY,
        REFERENCE_CANARY,
        GRADING_CANARY,
        "DATABASE_SCALAR_CANARY",
        "guide.md",
        "task.json",
    ):
        assert canary not in exposed


def test_inspection_cli_emits_exact_buffered_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print the deterministic inspection contract only after validation succeeds."""
    fixture = _create_local_fixture(tmp_path)
    _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)
    script = _inspection_script_module()

    exit_code = script.main([], project_root=fixture.project_root, config=fixture.config)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        f"tag: {TAG}",
        f"commit: {fixture.commit_sha}",
        "documents: 1",
        "tasks: 1",
        "database:",
        "  accounts: kind=object, count=1",
        "  active: kind=boolean",
        "  description: kind=string",
        "  empty: kind=null",
        "  flags: kind=array, count=0",
        "  version: kind=number",
    ]


def test_inspection_cli_rejects_usage_and_buffers_expected_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preserve argparse code two and emit no partial result on validation failure."""
    fixture = _create_local_fixture(tmp_path)
    script = _inspection_script_module()
    with pytest.raises(SystemExit) as usage_error:
        script.main(["--checkout", "elsewhere"])
    assert usage_error.value.code == 2
    capsys.readouterr()

    exit_code = script.main([], project_root=fixture.project_root, config=fixture.config)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    assert captured.err == (
        "error[checkout-missing]: reason=Checkout is missing; run setup before inspection; "
        f"path={json.dumps(str(checkout))}; "
        "recovery=run setup without --check before retrying\n"
    )
    assert "Traceback" not in captured.err
    assert not (fixture.project_root / ".cache").exists()


@pytest.mark.parametrize(
    "change_kind",
    ["git-state", "document-count", "task-count", "database-shape"],
)
def test_inspection_detects_changed_second_observation_without_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    change_kind: str,
) -> None:
    """Reject identity, count, and shape changes without printing a partial summary."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    before = _snapshot_tree(checkout)
    original_validate: Callable[
        [Path, Tau3Config, ResolvedTau3Paths],
        tuple[GitCheckoutState, BankingDataState],
    ] = module._validate_checkout
    observations = 0

    def changed_second_observation(
        project_root: Path,
        config: Tau3Config,
        paths: ResolvedTau3Paths,
    ) -> tuple[GitCheckoutState, BankingDataState]:
        """Inject a count change in the second otherwise valid observation."""
        nonlocal observations
        git_state, data_state = original_validate(project_root, config, paths)
        observations += 1
        if observations == 2:
            if change_kind == "git-state":
                git_state = GitCheckoutState(
                    git_state.top_level,
                    git_state.origin_url,
                    "0" * 40,
                    git_state.tag_sha,
                    git_state.is_clean,
                )
            elif change_kind == "document-count":
                data_state = BankingDataState(
                    data_state.document_count + 1,
                    data_state.task_count,
                    data_state.database_collections,
                )
            elif change_kind == "task-count":
                data_state = BankingDataState(
                    data_state.document_count,
                    data_state.task_count + 1,
                    data_state.database_collections,
                )
            else:
                data_state = BankingDataState(
                    data_state.document_count,
                    data_state.task_count,
                    (
                        *data_state.database_collections,
                        DatabaseCollectionShape("changed", "array", 0),
                    ),
                )
        return git_state, data_state

    monkeypatch.setattr(module, "_validate_checkout", changed_second_observation)
    script = _inspection_script_module()
    monkeypatch.setattr(script, "inspect_tau3_data", module.inspect_tau3_data)

    exit_code = script.main([], project_root=fixture.project_root, config=fixture.config)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("error[checkout-changed]:")
    assert "Traceback" not in captured.err
    assert _snapshot_tree(checkout) == before


@pytest.mark.parametrize(
    "variant",
    [
        "missing-database",
        "malformed-database",
        "empty-database-object",
        "documents-file",
        "tasks-missing",
    ],
)
def test_first_install_rejects_invalid_required_data_without_promotion(
    tmp_path: Path,
    variant: str,
) -> None:
    """Reject missing, wrong-kind, or malformed banking data before promotion."""
    fixture = _create_local_fixture(tmp_path, variant=variant)
    module = _tau3_module()

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category in {"banking-data-invalid", "malformed-database"}
    assert not (fixture.project_root / ".cache" / "tau3-bench").exists()
    assert DOCUMENT_CANARY not in str(raised.value)
    assert RECORD_CANARY not in str(raised.value)
    assert TASK_CANARY not in str(raised.value)


def test_first_install_is_independent_of_process_current_directory(tmp_path: Path) -> None:
    """Anchor acquisition to the explicit project root while called elsewhere."""
    fixture = _create_local_fixture(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    with _changed_directory(elsewhere):
        result = _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)

    assert result.mode == "installed"
    assert (fixture.project_root / ".cache" / "tau3-bench").is_dir()
    assert not (elsewhere / ".cache").exists()


def test_setup_cli_emits_stable_success_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Translate an installed result into deterministic stdout and exit code zero."""
    fixture = _create_local_fixture(tmp_path)
    environment_canary = "API_KEY_ENVIRONMENT_CANARY"
    monkeypatch.setenv("TAU3_API_KEY", environment_canary)
    script = _setup_script_module()

    exit_code = script.main([], project_root=fixture.project_root, config=fixture.config)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        "status: valid",
        "mode: installed",
        "checkout: .cache/tau3-bench/",
        f"tag: {TAG}",
        f"commit: {fixture.commit_sha}",
    ]
    assert environment_canary not in captured.out


def test_setup_cli_routes_expected_failure_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return one for expected setup failures without traceback or partial stdout."""
    fixture = _create_local_fixture(tmp_path, variant="missing-database")
    script = _setup_script_module()

    exit_code = script.main([], project_root=fixture.project_root, config=fixture.config)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("error[")
    assert "Traceback" not in captured.err


def test_setup_cli_emits_exact_centralized_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Render setup failures with category, safe path, reason, and recovery."""
    fixture = _create_local_fixture(tmp_path)
    script = _setup_script_module()

    exit_code = script.main(
        ["--check"],
        project_root=fixture.project_root,
        config=fixture.config,
    )

    checkout = fixture.project_root / ".cache" / "tau3-bench"
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "error[checkout-missing]: reason=Checkout is missing; run setup without --check; "
        f"path={json.dumps(str(checkout))}; "
        "recovery=run setup without --check before retrying\n"
    )


def test_setup_cli_preserves_argparse_usage_exit_two() -> None:
    """Reject unknown production overrides through argparse's usage contract."""
    script = _setup_script_module()

    with pytest.raises(SystemExit) as raised:
        script.main(["--repository-url", "https://example.invalid/repository.git"])

    assert raised.value.code == 2


def test_public_scripts_run_from_an_unrelated_working_directory(
    tmp_path: Path,
) -> None:
    """Run setup, check, and inspection through the locked copied project."""
    source_project = Path(__file__).resolve().parents[2]
    copied_project = tmp_path / "copied-project"
    unrelated_directory = tmp_path / "unrelated"
    copied_project.mkdir()
    unrelated_directory.mkdir()
    for directory_name in ("config", "scripts", "src"):
        shutil.copytree(source_project / directory_name, copied_project / directory_name)
    for file_name in (".python-version", "pyproject.toml", "uv.lock"):
        shutil.copy2(source_project / file_name, copied_project / file_name)
    target = copied_project / ".cache" / "tau3-bench"
    target.parent.mkdir()
    target.write_text("PREEXISTING_TARGET_CANARY", encoding="utf-8")
    uv_executable = shutil.which("uv")
    assert uv_executable is not None
    environment = {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in {"PYTHONPATH", "UV_PROJECT", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"}
    }
    synchronized = subprocess.run(  # noqa: S603
        [
            uv_executable,
            "sync",
            "--project",
            str(copied_project),
            "--locked",
            "--no-dev",
        ],
        cwd=unrelated_directory,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        shell=False,
        timeout=60,
    )
    assert synchronized.returncode == 0
    cases = (
        ("setup_tau3_data.py", (), "error[unexpected-target]:"),
        ("setup_tau3_data.py", ("--check",), "error[unexpected-target]:"),
        ("inspect_tau3_banking_data.py", (), "error[unexpected-target]:"),
    )

    for script_name, arguments, expected_error in cases:
        script_path = copied_project / "scripts" / script_name
        result = subprocess.run(  # noqa: S603
            [
                uv_executable,
                "run",
                "--project",
                str(copied_project),
                "--locked",
                "--no-dev",
                "python",
                str(script_path),
                *arguments,
            ],
            cwd=unrelated_directory,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            shell=False,
            timeout=60,
        )

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr.startswith(expected_error)
        assert "Traceback" not in result.stderr
        assert target.read_text(encoding="utf-8") == "PREEXISTING_TARGET_CANARY"


def test_existing_and_check_modes_are_offline_and_byte_stable(tmp_path: Path) -> None:
    """Reuse a valid checkout without remote access, locks, staging, or byte changes."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    before = _snapshot_tree(checkout)
    unavailable_remote = fixture.bare_remote.with_name("remote-unavailable.git")
    fixture.bare_remote.rename(unavailable_remote)

    existing = module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checked = module.setup_tau3_data(
        fixture.project_root,
        config=fixture.config,
        check_only=True,
    )

    assert existing.mode == "existing"
    assert checked.mode == "check"
    assert _snapshot_tree(checkout) == before
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


@pytest.mark.parametrize("check_only", [False, True])
def test_invalid_existing_checkout_is_offline_and_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    check_only: bool,
) -> None:
    """Validate invalid existing state offline in both default and check modes."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    (checkout / "OFFLINE_DIRTY_CANARY.txt").write_text("dirty", encoding="utf-8")
    before = _snapshot_tree(checkout)
    fixture.bare_remote.rename(fixture.bare_remote.with_name("remote-unavailable.git"))
    original_run_git: Callable[..., str] = module._run_git

    def reject_network_git(
        arguments: Sequence[str],
        *,
        cwd: Path,
        failure_category: str,
    ) -> str:
        """Fail the test if validation attempts a network-capable Git operation."""
        assert not arguments or arguments[0] not in {"clone", "fetch", "pull"}
        return original_run_git(arguments, cwd=cwd, failure_category=failure_category)

    monkeypatch.setattr(module, "_run_git", reject_network_git)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(
            fixture.project_root,
            config=fixture.config,
            check_only=check_only,
        )

    assert raised.value.category == "dirty-checkout"
    assert _snapshot_tree(checkout) == before
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


def test_check_missing_checkout_creates_no_cache_or_runtime_state(tmp_path: Path) -> None:
    """Return checkout-missing without creating the cache, lock, or staging state."""
    fixture = _create_local_fixture(tmp_path)

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().setup_tau3_data(
            fixture.project_root,
            config=fixture.config,
            check_only=True,
        )

    assert raised.value.category == "checkout-missing"
    assert not (fixture.project_root / ".cache").exists()


def test_unexpected_target_reports_expected_and_detected_kinds(tmp_path: Path) -> None:
    """Describe a wrong-kind target without changing or disclosing its contents."""
    fixture = _create_local_fixture(tmp_path)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    checkout.parent.mkdir()
    checkout.write_text("UNEXPECTED_TARGET_CONTENT_CANARY", encoding="utf-8")

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "unexpected-target"
    assert raised.value.message == (
        "Expected checkout to be a real directory; detected regular file"
    )
    assert "UNEXPECTED_TARGET_CONTENT_CANARY" not in str(raised.value)


def test_origin_mismatch_reports_credential_redacted_detected_origin(tmp_path: Path) -> None:
    """Report expected and sanitized detected origins while preserving Git state."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    credential_canary = "URL_PASSWORD_CANARY"
    detected = f"https://user:{credential_canary}@example.invalid/mirror.git"
    _run_git("remote", "set-url", "origin", detected, cwd=checkout)
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "origin-mismatch"
    assert fixture.config.upstream.repository_url in str(raised.value)
    assert "https://example.invalid/mirror.git" in str(raised.value)
    assert "user" not in str(raised.value)
    assert credential_canary not in str(raised.value)
    assert _snapshot_tree(checkout) == before


def test_revision_mismatch_reports_expected_and_detected_full_shas(tmp_path: Path) -> None:
    """Return both full revisions without repairing or changing the checkout."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    wrong_sha = "0" * 40
    wrong_config = Tau3Config(
        schema_version=fixture.config.schema_version,
        upstream=Tau3UpstreamConfig(
            fixture.config.upstream.repository_url,
            fixture.config.upstream.license_id,
            fixture.config.upstream.tag,
            wrong_sha,
        ),
        paths=fixture.config.paths,
    )
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=wrong_config)

    assert raised.value.category == "revision-mismatch"
    assert wrong_sha in str(raised.value)
    assert fixture.commit_sha in str(raised.value)
    assert _snapshot_tree(checkout) == before


@pytest.mark.parametrize("change_kind", ["tracked", "untracked"])
def test_dirty_checkout_diagnostic_never_discloses_changed_paths(
    tmp_path: Path,
    change_kind: str,
) -> None:
    """Reject local changes without printing porcelain entries or filenames."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    filename_canary = "DIRTY_FILENAME_CANARY.txt"
    if change_kind == "tracked":
        changed = checkout / "data" / "tau2" / "domains" / "banking_knowledge" / "db.json"
        changed.write_text('{"changed": true}', encoding="utf-8")
    else:
        (checkout / filename_canary).write_text("dirty", encoding="utf-8")
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "dirty-checkout"
    assert "detected 1 status entry" in raised.value.message
    assert change_kind in raised.value.message
    assert filename_canary not in str(raised.value)
    assert "db.json" not in str(raised.value)
    assert _snapshot_tree(checkout) == before


def test_preexisting_lock_and_stale_staging_are_preserved(tmp_path: Path) -> None:
    """Block setup on unowned recovery state without removing any bytes."""
    fixture = _create_local_fixture(tmp_path)
    cache = fixture.project_root / ".cache"
    cache.mkdir()
    lock = cache / "tau3-bench.setup.lock"
    lock.mkdir()
    (lock / "owner.txt").write_text("LOCK_OWNER_CANARY", encoding="utf-8")
    stale = cache / "tau3-bench-staging-stale"
    stale.mkdir()
    (stale / "state.txt").write_text("STALE_STATE_CANARY", encoding="utf-8")
    before = _snapshot_tree(cache)

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "setup-locked"
    assert _snapshot_tree(cache) == before


def test_failed_clone_removes_only_current_owned_state(tmp_path: Path) -> None:
    """Clean a failed clone while preserving unrelated staging and final absence."""
    fixture = _create_local_fixture(tmp_path)
    fixture.bare_remote.rename(fixture.bare_remote.with_name("unavailable.git"))
    cache = fixture.project_root / ".cache"
    cache.mkdir()
    unrelated = cache / "tau3-bench-staging-unrelated"
    unrelated.mkdir()
    (unrelated / "canary.txt").write_text("UNRELATED_STAGING_CANARY", encoding="utf-8")
    before_unrelated = _snapshot_tree(unrelated)

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "clone-failed"
    assert not (cache / "tau3-bench").exists()
    assert not (cache / "tau3-bench.setup.lock").exists()
    assert _snapshot_tree(unrelated) == before_unrelated
    assert list(cache.glob("tau3-bench-staging-*")) == [unrelated]


def test_no_replace_promotion_preserves_an_empty_competing_directory(tmp_path: Path) -> None:
    """Reject even an empty destination without consuming the staged source."""
    module = _tau3_module()
    staged_checkout = tmp_path / "staged-checkout"
    destination = tmp_path / "destination"
    staged_checkout.mkdir()
    (staged_checkout / "owned.txt").write_text("STAGED_OWNER_CANARY", encoding="utf-8")
    destination.mkdir()
    destination_identity = destination.stat().st_ino

    with pytest.raises(FileExistsError):
        module._rename_directory_no_replace(staged_checkout, destination)

    assert destination.stat().st_ino == destination_identity
    assert not list(destination.iterdir())
    assert (staged_checkout / "owned.txt").read_text(encoding="utf-8") == ("STAGED_OWNER_CANARY")


def test_destination_created_inside_promotion_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close the final absence-check race with the atomic no-replace primitive."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    original_promote: Callable[[Path, Path], None] = module._rename_directory_no_replace
    destination = fixture.project_root / ".cache" / "tau3-bench"
    destination_identity: int | None = None

    def promote_with_race(source: Path, target: Path) -> None:
        """Create a competing empty directory in the final promotion window."""
        nonlocal destination_identity
        assert target == destination
        target.mkdir()
        destination_identity = target.stat().st_ino
        original_promote(source, target)

    monkeypatch.setattr(module, "_rename_directory_no_replace", promote_with_race)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "destination-conflict"
    assert destination_identity is not None
    assert destination.stat().st_ino == destination_identity
    assert not list(destination.iterdir())
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


def test_destination_appearance_is_preserved_and_aborts_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve a destination created after staging validation and remove owned state."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    original_validate: Callable[
        [Path, Tau3Config, ResolvedTau3Paths],
        tuple[GitCheckoutState, BankingDataState],
    ] = module._validate_checkout
    destination = fixture.project_root / ".cache" / "tau3-bench"

    def validate_with_race(
        project_root: Path,
        config: Tau3Config,
        paths: ResolvedTau3Paths,
    ) -> object:
        """Create the competing destination after staged validation."""
        result = original_validate(project_root, config, paths)
        checkout = paths.checkout
        if "tau3-bench-staging-" in str(checkout):
            destination.mkdir()
            (destination / "owner.txt").write_text("DESTINATION_OWNER_CANARY", encoding="utf-8")
        return result

    monkeypatch.setattr(module, "_validate_checkout", validate_with_race)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "destination-conflict"
    assert (destination / "owner.txt").read_text(encoding="utf-8") == "DESTINATION_OWNER_CANARY"
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


def test_post_promotion_failure_preserves_promoted_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain a fully promoted checkout when final revalidation reports failure."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    original_validate: Callable[
        [Path, Tau3Config, ResolvedTau3Paths],
        tuple[GitCheckoutState, BankingDataState],
    ] = module._validate_checkout
    destination = fixture.project_root / ".cache" / "tau3-bench"

    def fail_final_validation(
        project_root: Path,
        config: Tau3Config,
        paths: ResolvedTau3Paths,
    ) -> tuple[GitCheckoutState, BankingDataState]:
        """Fail only after the staged checkout has become the final destination."""
        if paths.checkout == destination and destination.exists():
            raise Tau3OperationError(
                "checkout-changed",
                "Final checkout validation did not remain stable",
                destination,
            )
        return original_validate(project_root, config, paths)

    monkeypatch.setattr(module, "_validate_checkout", fail_final_validation)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "checkout-changed"
    assert destination.is_dir()
    assert _run_git("rev-parse", "HEAD", cwd=destination).stdout.strip() == fixture.commit_sha
    assert not (fixture.project_root / ".cache" / "tau3-bench.setup.lock").exists()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


@pytest.mark.parametrize(
    "target_kind",
    [
        "checkout-file",
        "cache-file",
        "checkout-reparse",
        "cache-reparse",
        "checkout-special",
        "cache-special",
    ],
)
def test_unexpected_target_kinds_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_kind: str,
) -> None:
    """Reject wrong-kind cache boundaries without changing neighboring state."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    cache = fixture.project_root / ".cache"
    boundary = cache / "tau3-bench" if target_kind.startswith("checkout-") else cache
    if target_kind.endswith("-file"):
        if boundary == cache / "tau3-bench":
            cache.mkdir()
        boundary.write_text("BOUNDARY_FILE_CANARY", encoding="utf-8")
    else:
        boundary.mkdir(parents=True)
    if target_kind.endswith("-reparse"):
        monkeypatch.setattr(module, "_is_reparse_point", lambda _path_stat: True)
    elif target_kind.endswith("-special"):
        original_lstat: Callable[[Path], os.stat_result] = Path.lstat
        special_stat = os.stat_result((stat.S_IFIFO | 0o600, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def lstat_special(path: Path) -> os.stat_result:
            """Classify only the selected cache boundary as a special object."""
            if path == boundary:
                return special_stat
            return original_lstat(path)

        monkeypatch.setattr(Path, "lstat", lstat_special)
    neighbor = fixture.project_root / "neighbor.txt"
    neighbor.write_text("NEIGHBOR_CANARY", encoding="utf-8")
    before = _snapshot_tree(fixture.project_root)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "unexpected-target"
    assert _snapshot_tree(fixture.project_root) == before


def test_reparse_classification_uses_the_shared_non_following_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise Windows junction/reparse rejection without requiring host privileges."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    module = _tau3_module()
    monkeypatch.setattr(module, "_is_reparse_point", lambda _path_stat: True)

    with pytest.raises(Tau3OperationError) as raised:
        module._require_real_directory(checkout, tmp_path, "checkout")

    assert raised.value.category == "unexpected-target"
    assert checkout.is_dir()


def test_unicode_and_opaque_names_are_counted_without_disclosure(tmp_path: Path) -> None:
    """Keep traversal UTF-8 and locale-independent while treating names as opaque."""
    checkout = tmp_path / "checkout"
    documents = checkout / "documents"
    nested = documents / "τ³-银行"
    nested.mkdir(parents=True)
    filename_canary = "OPAQUE_FILENAME_CANARY-é.md"
    (nested / filename_canary).write_text("body", encoding="utf-8")

    assert _tau3_module()._count_readable_files(documents, checkout, "documents") == 1

    (nested / filename_canary).unlink()
    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module()._count_readable_files(documents, checkout, "documents")
    assert filename_canary not in str(raised.value)


def test_host_path_length_failure_is_categorized_without_path_contents(tmp_path: Path) -> None:
    """Fail safely when the host rejects an unrepresentable path component."""
    component_canary = "PATH_COMPONENT_CANARY" * 30
    path = tmp_path / component_canary

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module()._path_lstat(path)

    assert raised.value.category == "unexpected-target"
    assert component_canary not in str(raised.value)


@pytest.mark.parametrize("denied_operation", ["target-classification", "cache-create"])
def test_cache_and_target_permission_failures_are_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    denied_operation: str,
) -> None:
    """Categorize injected cache/target permission failures without mutation."""
    fixture = _create_local_fixture(tmp_path)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    cache = fixture.project_root / ".cache"
    original_lstat: Callable[[Path], os.stat_result] = Path.lstat
    original_mkdir = Path.mkdir

    def deny_target_lstat(path: Path) -> os.stat_result:
        """Deny only the configured target classification."""
        if denied_operation == "target-classification" and path == checkout:
            raise PermissionError("injected target denial")
        return original_lstat(path)

    def deny_cache_mkdir(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        """Deny only creation of the configured cache root."""
        if denied_operation == "cache-create" and path == cache:
            raise PermissionError("injected cache denial")
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "lstat", deny_target_lstat)
    monkeypatch.setattr(Path, "mkdir", deny_cache_mkdir)

    with pytest.raises(Tau3OperationError) as raised:
        _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "unexpected-target"
    assert not checkout.exists()
    assert not (cache / "tau3-bench.setup.lock").exists()
    if cache.exists():
        assert not list(cache.glob("tau3-bench-staging-*"))


def test_path_resolution_preserves_configured_case_without_casefolding(tmp_path: Path) -> None:
    """Use filesystem containment semantics without trusting case-folded path strings."""
    fixture = _create_local_fixture(tmp_path)
    mixed_case_root = ".cache/Tau3-Bench/"
    config = Tau3Config(
        fixture.config.schema_version,
        fixture.config.upstream,
        Tau3PathConfig(
            checkout=mixed_case_root,
            documents=f"{mixed_case_root}data/documents/",
            database=f"{mixed_case_root}data/db.json",
            tasks=f"{mixed_case_root}data/tasks/",
        ),
    )

    paths = _tau3_module().resolve_tau3_paths(fixture.project_root, config)

    assert paths.checkout.name == "Tau3-Bench"
    assert paths.documents.is_relative_to(paths.checkout)
    assert paths.database.is_relative_to(paths.checkout)
    assert paths.tasks.is_relative_to(paths.checkout)


def test_two_concurrent_setups_preserve_lock_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow one setup owner and reject its concurrent peer without cleanup interference."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    original_run_git: Callable[..., str] = module._run_git
    clone_entered = threading.Event()
    release_clone = threading.Event()
    worker_errors: list[BaseException] = []

    def blocking_run_git(
        arguments: Sequence[str],
        *,
        cwd: Path,
        failure_category: str,
    ) -> str:
        """Hold the owning clone while the competing setup observes its lock."""
        if arguments and arguments[0] == "clone":
            clone_entered.set()
            if not release_clone.wait(timeout=10):
                raise RuntimeError("test clone barrier timed out")
        return original_run_git(arguments, cwd=cwd, failure_category=failure_category)

    def install() -> None:
        """Run the lock-owning setup and retain unexpected worker errors."""
        try:
            module.setup_tau3_data(fixture.project_root, config=fixture.config)
        except BaseException as error:  # pragma: no cover - asserted after thread join
            worker_errors.append(error)

    monkeypatch.setattr(module, "_run_git", blocking_run_git)
    worker = threading.Thread(target=install)
    worker.start()
    assert clone_entered.wait(timeout=10)
    try:
        with pytest.raises(Tau3OperationError) as raised:
            module.setup_tau3_data(fixture.project_root, config=fixture.config)
        assert raised.value.category == "setup-locked"
    finally:
        release_clone.set()
        worker.join(timeout=20)

    assert not worker.is_alive()
    assert worker_errors == []
    assert (fixture.project_root / ".cache" / "tau3-bench").is_dir()


def test_cleanup_failure_reports_owned_state_without_removing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain current-run recovery evidence when staging cleanup itself fails."""
    fixture = _create_local_fixture(tmp_path)
    unavailable = fixture.bare_remote.with_name("unavailable.git")
    fixture.bare_remote.rename(unavailable)
    module = _tau3_module()

    def deny_cleanup(
        _path: Path,
        *,
        onexc: Callable[[Callable[[str], object], str, BaseException], None],
    ) -> None:
        """Inject a deterministic cleanup permission failure."""
        del onexc
        raise PermissionError("injected cleanup denial")

    monkeypatch.setattr(module.shutil, "rmtree", deny_cleanup)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    cache = fixture.project_root / ".cache"
    assert raised.value.category == "staging-cleanup-failed"
    assert (cache / "tau3-bench.setup.lock").is_dir()
    assert len(list(cache.glob("tau3-bench-staging-*"))) == 1
    assert not (cache / "tau3-bench").exists()


def test_lock_cleanup_failure_reports_the_retained_lock_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report the lock rather than the removed staging parent when lock cleanup fails."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    lock = fixture.project_root / ".cache" / "tau3-bench.setup.lock"
    original_rmdir = Path.rmdir

    def deny_lock_cleanup(path: Path) -> None:
        """Inject a deterministic failure only for the owned setup lock."""
        if path == lock:
            raise PermissionError("injected lock cleanup denial")
        original_rmdir(path)

    monkeypatch.setattr(module.Path, "rmdir", deny_lock_cleanup)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "staging-cleanup-failed"
    assert raised.value.path == lock
    assert lock.is_dir()
    assert (fixture.project_root / ".cache" / "tau3-bench").is_dir()
    assert not list((fixture.project_root / ".cache").glob("tau3-bench-staging-*"))


def test_invalid_existing_repository_and_tag_binding_are_distinct(
    tmp_path: Path,
) -> None:
    """Distinguish a non-repository from a repository missing the approved tag."""
    fixture = _create_local_fixture(tmp_path)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    checkout.mkdir(parents=True)
    (checkout / "owner.txt").write_text("OWNER_CANARY", encoding="utf-8")
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as not_repository:
        _tau3_module().setup_tau3_data(fixture.project_root, config=fixture.config)
    assert not_repository.value.category == "not-standalone-repository"
    assert _snapshot_tree(checkout) == before

    shutil.rmtree(checkout)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    _run_git("tag", "--delete", TAG, cwd=checkout)
    tag_before = _snapshot_tree(checkout)
    with pytest.raises(Tau3OperationError) as tag_error:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)
    assert tag_error.value.category == "tag-mismatch"
    assert _snapshot_tree(checkout) == tag_before


def test_wrong_existing_tag_binding_reports_expected_and_detected_shas(tmp_path: Path) -> None:
    """Reject a present approved tag that resolves to the wrong commit object."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    tree_sha = _run_git("rev-parse", "HEAD^{tree}", cwd=checkout).stdout.strip()
    alternate_sha = _run_git(
        "-c",
        "user.name=VerityCX Test",
        "-c",
        "user.email=veritycx-test@example.invalid",
        "commit-tree",
        tree_sha,
        "-m",
        "Create alternate tag target",
        cwd=checkout,
    ).stdout.strip()
    _run_git("tag", "--force", TAG, alternate_sha, cwd=checkout)
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "tag-mismatch"
    assert fixture.commit_sha in raised.value.message
    assert alternate_sha in raised.value.message
    assert _snapshot_tree(checkout) == before


def test_multiple_origins_are_rejected_without_disclosing_values(tmp_path: Path) -> None:
    """Report only the number of conflicting origins and preserve repository metadata."""
    fixture = _create_local_fixture(tmp_path)
    module = _tau3_module()
    module.setup_tau3_data(fixture.project_root, config=fixture.config)
    checkout = fixture.project_root / ".cache" / "tau3-bench"
    credential_canary = "SECOND_ORIGIN_CREDENTIAL_CANARY"
    _run_git(
        "config",
        "--add",
        "remote.origin.url",
        f"https://user:{credential_canary}@example.invalid/second.git",
        cwd=checkout,
    )
    before = _snapshot_tree(checkout)

    with pytest.raises(Tau3OperationError) as raised:
        module.setup_tau3_data(fixture.project_root, config=fixture.config)

    assert raised.value.category == "origin-mismatch"
    assert "2 configured origins" in str(raised.value)
    assert credential_canary not in str(raised.value)
    assert _snapshot_tree(checkout) == before
