"""Exercise local Chatwoot ownership, privacy and offline preparation boundaries."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _command(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the actual CLI with no discoverable Docker executable."""
    return subprocess.run(  # noqa: S603 - fixed project command with synthetic test paths.
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/setup_chatwoot.py"),
            "--root",
            str(root),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("arguments", [(), ("--check",)])
def test_missing_docker_creates_no_state(tmp_path: Path, arguments: tuple[str, ...]) -> None:
    """A missing runtime must report a safe category and leave no generated credentials."""
    root = tmp_path / "chatwoot"
    result = _command(root, *arguments)
    assert result.returncode == 1
    assert result.stdout == "chatwoot_docker_missing\n"
    assert result.stderr == ""
    assert not root.exists()


def test_prepare_requires_explicit_private_network_opt_in(tmp_path: Path) -> None:
    """Offline preparation cannot silently disable private-network SSRF protection."""
    root = tmp_path / "chatwoot"
    result = _command(root, "--prepare")
    assert result.returncode == 1
    assert result.stdout == "chatwoot_local_webhooks_opt_in_required\n"
    assert result.stderr == ""
    assert not root.exists()


def test_prepare_reuses_private_credentials_without_app_config_changes(tmp_path: Path) -> None:
    """Preparation works offline, preserves secrets, and never prints secret material."""
    root = tmp_path / "chatwoot"
    first = _command(root, "--prepare", "--allow-local-webhooks")
    assert first.returncode == 0, first.stdout + first.stderr
    files = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
    credentials = json.loads((root / "credentials.json").read_text())
    environment = dotenv_values(root / "compose.env")
    assert environment["POSTGRES_PASSWORD"] == credentials["postgres_password"]
    assert environment["SAFE_FETCH_ALLOW_PRIVATE_NETWORK"] == "true"
    assert environment["FRONTEND_URL"] == "http://127.0.0.1:3000"
    assert environment["POSTGRES_DATABASE"] == "veritycx_chatwoot"
    assert not (root / "integration.json").exists()
    for name in ("admin_password", "postgres_password", "redis_password", "secret_key_base"):
        assert len(credentials[name]) >= 32
        assert credentials[name] not in first.stdout + first.stderr
    assert credentials["admin_email"].endswith("@veritycx.invalid")
    if os.name == "posix":
        assert root.stat().st_mode & 0o777 == 0o700
        assert all(
            path.stat().st_mode & 0o777 == 0o600 for path in root.iterdir() if path.is_file()
        )
    second = _command(root, "--prepare", "--allow-local-webhooks")
    assert second.returncode == 0
    assert {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()} == files


@pytest.mark.parametrize("linked", [False, True])
def test_prepare_refuses_unowned_or_linked_roots(tmp_path: Path, linked: bool) -> None:
    """An existing unrelated directory must not be claimed, chmodded or populated."""
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    canary = directory / "keep"
    canary.write_text("untouched")
    root = tmp_path / "chatwoot" if linked else directory
    if linked:
        try:
            root.symlink_to(directory, target_is_directory=True)
        except OSError:
            pytest.skip("local symlink privilege required")
    result = _command(root, "--prepare", "--allow-local-webhooks")
    assert result.returncode == 1
    assert result.stdout == "chatwoot_setup_unowned\n"
    assert result.stderr == ""
    assert list(directory.iterdir()) == [canary]
    assert canary.read_text() == "untouched"


def test_prepare_refuses_lost_credentials(tmp_path: Path) -> None:
    """A marked installation must not rotate missing passwords behind existing volumes."""
    root = tmp_path / "chatwoot"
    assert _command(root, "--prepare", "--allow-local-webhooks").returncode == 0
    (root / "credentials.json").unlink()
    result = _command(root, "--prepare", "--allow-local-webhooks")
    assert result.returncode == 1
    assert result.stdout == "chatwoot_credentials_invalid\n"
    assert not (root / "credentials.json").exists()


def test_application_config_preserves_unrelated_settings_and_refuses_conflicts(
    tmp_path: Path,
) -> None:
    """Connecting Chatwoot must keep the approved provider key and reject changed bindings."""
    from scripts import setup_chatwoot as setup

    path = tmp_path / ".env"
    path.write_text("# preserved\nOPENAI_API_KEY='synthetic-keep'\nVERITYCX_CHATWOOT_URL=\n")
    result = {
        "account_id": 7,
        "inbox_id": 12,
        "website_token": "synthetic-public",
        "api_token": "synthetic-private",
        "bot_token": "synthetic-bot-private",
        "webhook_secret": "synthetic-signing",
    }
    setup.write_application_environment(path, result)
    before = path.read_bytes()
    setup.write_application_environment(path, result)
    assert path.read_bytes() == before
    values = dotenv_values(path)
    assert values["OPENAI_API_KEY"] == "synthetic-keep"
    assert values["VERITYCX_CHATWOOT_ACCOUNT_ID"] == "7"
    assert values["VERITYCX_CHATWOOT_INBOX_ID"] == "12"
    assert values["VERITYCX_CHATWOOT_API_TOKEN"] == "synthetic-private"  # noqa: S105 - fixture.
    assert values["VERITYCX_CHATWOOT_BOT_TOKEN"] == "synthetic-bot-private"  # noqa: S105 - fixture.
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(setup.ChatwootSetupError, match="chatwoot_app_configuration_conflict"):
        setup.write_application_environment(path, {**result, "inbox_id": 13})
    assert path.read_bytes() == before


def test_ownership_guard_rejects_foreign_volume_before_commands(tmp_path: Path) -> None:
    """A fixed Compose volume name cannot be adopted based only on its project name."""
    from scripts import setup_chatwoot as setup

    metadata = {"Labels": {"com.docker.compose.project": "veritycx-chatwoot"}}
    with pytest.raises(setup.ChatwootSetupError, match="chatwoot_setup_unowned"):
        setup.validate_resource_ownership(metadata, "synthetic-owner")
    metadata["Labels"]["io.veritycx.chatwoot.owner"] = "another-owner"
    with pytest.raises(setup.ChatwootSetupError, match="chatwoot_setup_unowned"):
        setup.validate_resource_ownership(metadata, "synthetic-owner")


def test_private_runner_returns_only_current_output(tmp_path: Path) -> None:
    """A successful command without a result cannot reuse credentials from an earlier run."""
    from scripts import setup_chatwoot as setup

    (tmp_path / "setup.log").write_text('VERITYCX_RESULT={"api_token":"old-secret"}\n')
    content = setup._run_private([sys.executable, "-c", "print('current-output')"], tmp_path)
    assert content == "current-output\n"
    assert "old-secret" in (tmp_path / "setup.log").read_text()
    if os.name == "posix":
        assert (tmp_path / "setup.log").stat().st_mode & 0o777 == 0o600


def test_private_runner_captures_failure_without_disclosing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Even failing Rails diagnostics must stay in a private file, outside CLI output."""
    from scripts import setup_chatwoot as setup

    with pytest.raises(setup.ChatwootSetupError, match="chatwoot_compose_failed"):
        setup._run_private(
            [sys.executable, "-c", "import sys; print('synthetic-private-output'); sys.exit(1)"],
            tmp_path,
        )
    assert capsys.readouterr().out == ""
    assert "synthetic-private-output" in (tmp_path / "setup.log").read_text()


def test_prepare_refuses_redirected_credentials(tmp_path: Path) -> None:
    """A secret-file symlink must not cause a write or chmod on an unrelated target."""
    root = tmp_path / "chatwoot"
    assert _command(root, "--prepare", "--allow-local-webhooks").returncode == 0
    target = tmp_path / "elsewhere.json"
    (root / "credentials.json").rename(target)
    before = target.read_bytes()
    try:
        (root / "credentials.json").symlink_to(target)
    except OSError:
        pytest.skip("local symlink privilege required")
    result = _command(root, "--prepare", "--allow-local-webhooks")
    assert result.returncode == 1
    assert result.stdout == "chatwoot_setup_unowned\n"
    assert target.read_bytes() == before


def test_application_config_rejects_nonpositive_and_boolean_ids(tmp_path: Path) -> None:
    """Malformed provisioner output must not silently become application credentials."""
    from scripts import setup_chatwoot as setup

    for identifier in (False, 0, -1, "3"):
        with pytest.raises(setup.ChatwootSetupError, match="chatwoot_provision_result_invalid"):
            setup.write_application_environment(
                tmp_path / ".env",
                {
                    "account_id": identifier,
                    "inbox_id": 2,
                    "website_token": "synthetic-public",
                    "api_token": "synthetic-private",
                    "bot_token": "synthetic-bot-private",
                    "webhook_secret": "synthetic-signing",
                },
            )
    assert not (tmp_path / ".env").exists()


@pytest.mark.skipif(os.name != "posix", reason="fake executable requires POSIX shebang support")
def test_docker_preflight_failure_is_safe_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real failing subprocess must not expose daemon diagnostics or generate credentials."""
    from scripts import setup_chatwoot as setup

    executable = tmp_path / "docker"
    executable.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "if sys.argv[1:] == ['compose', 'version']:\n    sys.exit(0)\n"
        "print('synthetic-daemon-secret', file=sys.stderr)\nsys.exit(1)\n"
    )
    executable.chmod(0o700)
    root = tmp_path / "chatwoot"
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["setup_chatwoot.py", "--root", str(root)])
    assert setup.main() == 1
    output = capsys.readouterr()
    assert output.out == "chatwoot_docker_unavailable\n"
    assert output.err == ""
    assert not root.exists()


@pytest.mark.skipif(os.name != "posix", reason="fake executable requires POSIX shebang support")
def test_foreign_docker_volume_stops_bootstrap_before_file_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reachable daemon with an unowned reserved volume cannot be mutated or adopted."""
    from scripts import setup_chatwoot as setup

    executable = tmp_path / "docker"
    executable.write_text(
        f"#!{sys.executable}\nimport json, sys\nargs=sys.argv[1:]\n"
        "if args == ['compose', 'version']: sys.exit(0)\n"
        "if args == ['info', '--format', '{{.OSType}}']: print('linux'); sys.exit(0)\n"
        "if args[:2] == ['ps', '-aq']: sys.exit(0)\n"
        "if args[:2] == ['volume', 'ls']: print('veritycx-chatwoot_postgres_data'); sys.exit(0)\n"
        "if args == ['volume', 'inspect', 'veritycx-chatwoot_postgres_data']:\n"
        "    print(json.dumps([{'Labels': {'com.docker.compose.project': 'veritycx-chatwoot'}}]))\n"
        "    sys.exit(0)\n"
        "raise RuntimeError('unexpected Docker mutation')\n"
    )
    executable.chmod(0o700)
    root = tmp_path / "chatwoot"
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(
        sys, "argv", ["setup_chatwoot.py", "--root", str(root), "--allow-local-webhooks"]
    )
    assert setup.main() == 1
    output = capsys.readouterr()
    assert output.out == "chatwoot_setup_unowned\n"
    assert output.err == ""
    assert not root.exists()


def test_owned_resource_accepts_matching_installation_label() -> None:
    """An existing project-owned container can be reused when both ownership labels agree."""
    from scripts import setup_chatwoot as setup

    setup.validate_resource_ownership(
        {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "veritycx-chatwoot",
                    "io.veritycx.chatwoot.owner": "synthetic-owner",
                }
            }
        },
        "synthetic-owner",
    )


@pytest.mark.skipif(os.name != "posix", reason="fake executable requires POSIX shebang support")
def test_full_setup_connects_real_private_config_and_runs_app_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Successful external provisioning must connect actual IDs and migrate before success."""
    from scripts import setup_chatwoot as setup

    executable = tmp_path / "docker"
    executable.write_text(
        f"#!{sys.executable}\nimport json, sys\nargs=sys.argv[1:]\n"
        "if args == ['compose', 'version']: sys.exit(0)\n"
        "if args == ['info', '--format', '{{.OSType}}']: print('linux'); sys.exit(0)\n"
        "if args[:2] == ['ps', '-aq'] or args[:2] == ['volume', 'ls']: sys.exit(0)\n"
        "if args[-2:] == ['runner', '/run/veritycx/provision.rb']:\n"
        "    print('VERITYCX_RESULT=' + json.dumps({'account_id': 9, 'inbox_id': 14,\n"
        "          'website_token': 'synthetic-public', 'api_token': 'synthetic-user-token',\n"
        "          'bot_token': 'synthetic-bot-token',\n"
        "          'webhook_secret': 'synthetic-signing-secret'}))\n"
        "sys.exit(0)\n"
    )
    executable.chmod(0o700)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "manage_support.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "assert sys.argv[1:] == ['db', 'migrate']\n"
        "Path(__file__).with_name('migration-complete').touch()\n"
    )
    app_environment = tmp_path / ".env"
    app_environment.write_text("OPENAI_API_KEY='synthetic-preserved'\n")
    root = tmp_path / "chatwoot"
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(setup, "PROJECT_ROOT", tmp_path)
    # This test replaces the external runtime; existing developer listeners are unrelated.
    monkeypatch.setattr(setup, "_free_ports", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["setup_chatwoot.py", "--root", str(root), "--allow-local-webhooks"]
    )
    assert setup.main() == 0
    assert (scripts / "migration-complete").is_file()
    values = dotenv_values(app_environment)
    assert values["VERITYCX_CHATWOOT_ACCOUNT_ID"] == "9"
    assert values["VERITYCX_CHATWOOT_INBOX_ID"] == "14"
    assert values["VERITYCX_CHATWOOT_API_TOKEN"] == "synthetic-user-token"  # noqa: S105 - fixture.
    assert values["VERITYCX_CHATWOOT_BOT_TOKEN"] == "synthetic-bot-token"  # noqa: S105 - fixture.
    assert values["OPENAI_API_KEY"] == "synthetic-preserved"
    output = capsys.readouterr()
    assert output.out == f"chatwoot_setup_ready\nprivate_directory={root}\n"
    assert output.err == ""
    assert "synthetic-bot-token" in (root / "setup.log").read_text()


@pytest.mark.parametrize("bot_token", [None, "", False])
def test_application_config_requires_private_bot_token(tmp_path: Path, bot_token: object) -> None:
    """A missing publication credential must not produce a partially connected application."""
    from scripts import setup_chatwoot as setup

    result = {
        "account_id": 7,
        "inbox_id": 12,
        "website_token": "synthetic-public",
        "api_token": "synthetic-user",
        "webhook_secret": "synthetic-signing",
    }
    if bot_token is not None:
        result["bot_token"] = bot_token
    with pytest.raises(setup.ChatwootSetupError, match="chatwoot_provision_result_invalid"):
        setup.write_application_environment(tmp_path / ".env", result)
    assert not (tmp_path / ".env").exists()
