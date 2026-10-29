"""Provision an isolated, loopback-only Chatwoot deployment without privileged installation."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from veritycx.service.local_environment import (
    LocalSetupError,
    _app_environment_content,
    _write_app_environment,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / ".cache" / "support" / "chatwoot"
COMPOSE_FILE = PROJECT_ROOT / "config" / "chatwoot.compose.yml"
PROJECT = "veritycx-chatwoot"
VERSION = "v4.19.1"
OWNER_LABEL = "io.veritycx.chatwoot.owner"
MARKER = ".veritycx-chatwoot"
CREDENTIAL_KEYS = {
    "owner",
    "admin_email",
    "admin_password",
    "postgres_password",
    "redis_password",
    "secret_key_base",
}
RESULT_KEYS = {
    "account_id",
    "inbox_id",
    "website_token",
    "api_token",
    "bot_token",
    "webhook_secret",
}


class ChatwootSetupError(ValueError):
    """Expose a fixed safe operational failure category."""


def _read_json(path: Path) -> dict[str, Any]:
    """Read a private regular JSON object while rejecting links and malformed input."""
    if path.is_symlink() or not path.is_file():
        raise ChatwootSetupError("chatwoot_credentials_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ChatwootSetupError("chatwoot_credentials_invalid") from None
    if not isinstance(value, dict):
        raise ChatwootSetupError("chatwoot_credentials_invalid")
    return value


def _write_private(path: Path, content: str, *, exclusive: bool = False) -> None:
    """Create secret material with restrictive permissions before writing any bytes."""
    if path.is_symlink():
        raise ChatwootSetupError("chatwoot_setup_unowned")
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0)
        | (os.O_EXCL if exclusive else os.O_TRUNC),
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        if hasattr(os, "fchmod"):
            os.fchmod(output.fileno(), 0o600)
        else:
            path.chmod(0o600)
        output.write(content)


def _validate_root(root: Path) -> dict[str, Any] | None:
    """Refuse unrelated or redirected roots before any write or Docker mutation."""
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ChatwootSetupError("chatwoot_setup_unowned")
    if not root.exists():
        return None
    if not root.is_dir() or not (root / MARKER).is_file():
        raise ChatwootSetupError("chatwoot_setup_unowned")
    marker = _read_json(root / MARKER)
    if (
        set(marker) != {"format", "project", "version", "owner"}
        or marker.get("format") != 1
        or marker.get("project") != PROJECT
        or marker.get("version") != VERSION
        or not isinstance(marker.get("owner"), str)
        or not marker["owner"]
    ):
        raise ChatwootSetupError("chatwoot_setup_unowned")
    if any(path.is_symlink() for path in root.iterdir()):
        raise ChatwootSetupError("chatwoot_setup_unowned")
    return marker


def _credentials(root: Path, marker: dict[str, Any]) -> dict[str, str]:
    """Validate existing secrets without rotating passwords after partial data loss."""
    value = _read_json(root / "credentials.json")
    if (
        set(value) != CREDENTIAL_KEYS
        or any(not isinstance(value[key], str) or not value[key] for key in CREDENTIAL_KEYS)
        or value["owner"] != marker["owner"]
    ):
        raise ChatwootSetupError("chatwoot_credentials_invalid")
    return {key: str(value[key]) for key in CREDENTIAL_KEYS}


def _prepare(root: Path) -> dict[str, str]:
    """Create a private owned layout, preserving valid credentials on subsequent runs."""
    marker = _validate_root(root)
    if marker is None:
        credentials = {key: secrets.token_hex(32) for key in CREDENTIAL_KEYS}
        credentials["admin_email"] = "local-admin@veritycx.invalid"
        # Prefix guarantees the pinned Devise password complexity requirements.
        credentials["admin_password"] = "Vcx1!" + credentials["admin_password"]
        marker = {
            "format": 1,
            "project": PROJECT,
            "version": VERSION,
            "owner": credentials["owner"],
        }
        root.mkdir(parents=True, mode=0o700)
        _write_private(root / MARKER, json.dumps(marker, sort_keys=True) + "\n", exclusive=True)
        _write_private(
            root / "credentials.json",
            json.dumps(credentials, sort_keys=True) + "\n",
            exclusive=True,
        )
    else:
        credentials = _credentials(root, marker)
    root.chmod(0o700)
    values = {
        "VERITYCX_CHATWOOT_OWNER": credentials["owner"],
        "VERITYCX_CHATWOOT_LOCAL_ROOT": str(root),
        "POSTGRES_DB": "veritycx_chatwoot",
        "POSTGRES_DATABASE": "veritycx_chatwoot",
        "POSTGRES_USERNAME": "veritycx_chatwoot",
        "POSTGRES_PASSWORD": credentials["postgres_password"],
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "55433",
        "REDIS_URL": "redis://127.0.0.1:6380",
        "REDIS_PASSWORD": credentials["redis_password"],
        "SECRET_KEY_BASE": credentials["secret_key_base"],
        "FRONTEND_URL": "http://127.0.0.1:3000",
        "RAILS_ENV": "production",
        "NODE_ENV": "production",
        "INSTALLATION_ENV": "docker",
        "ACTIVE_STORAGE_SERVICE": "local",
        "ENABLE_ACCOUNT_SIGNUP": "false",
        "ENABLE_TELEMETRY": "false",
        "FORCE_SSL": "false",
        "RAILS_LOG_LEVEL": "warn",
        "RAILS_LOG_TO_STDOUT": "true",
        # CLI consent is required before this deliberately broad upstream setting is written.
        "SAFE_FETCH_ALLOW_PRIVATE_NETWORK": "true",
        "MAILER_SENDER_EMAIL": "VerityCX <local-admin@veritycx.invalid>",
    }
    try:
        _write_app_environment(root / "compose.env", values)
    except LocalSetupError:
        raise ChatwootSetupError("chatwoot_compose_configuration_conflict") from None
    for path in root.iterdir():
        if path.is_file():
            path.chmod(0o600)
    return credentials


def _validate_result(result: dict[str, Any]) -> None:
    """Validate provisioned IDs and secrets before connecting the application."""
    if (
        set(result) != RESULT_KEYS
        or any(
            type(result[key]) is not int or result[key] <= 0 for key in ("account_id", "inbox_id")
        )
        or any(
            not isinstance(result[key], str) or not result[key]
            for key in ("website_token", "api_token", "bot_token", "webhook_secret")
        )
    ):
        raise ChatwootSetupError("chatwoot_provision_result_invalid")


def _application_values(result: dict[str, Any]) -> dict[str, str]:
    """Translate provisioned resources into the seven supported application settings."""
    _validate_result(result)
    return {
        "VERITYCX_CHATWOOT_URL": "http://127.0.0.1:3000",
        "VERITYCX_CHATWOOT_ACCOUNT_ID": str(result["account_id"]),
        "VERITYCX_CHATWOOT_INBOX_ID": str(result["inbox_id"]),
        "VERITYCX_CHATWOOT_WEBSITE_TOKEN": result["website_token"],
        "VERITYCX_CHATWOOT_API_TOKEN": result["api_token"],
        "VERITYCX_CHATWOOT_BOT_TOKEN": result["bot_token"],
        "VERITYCX_CHATWOOT_WEBHOOK_SECRET": result["webhook_secret"],
    }


def write_application_environment(path: Path, result: dict[str, Any]) -> None:
    """Fill Chatwoot settings atomically without changing unrelated provider credentials."""
    try:
        _write_app_environment(path, _application_values(result))
    except LocalSetupError:
        raise ChatwootSetupError("chatwoot_app_configuration_conflict") from None


def _docker() -> str:
    """Check the CLI, Compose plugin and reachable daemon without changing local files."""
    executable = shutil.which("docker")
    if executable is None:
        raise ChatwootSetupError("chatwoot_docker_missing")
    for arguments, category in (
        (["compose", "version"], "chatwoot_compose_missing"),
        (["info", "--format", "{{.OSType}}"], "chatwoot_docker_unavailable"),
    ):
        result = subprocess.run(  # noqa: S603 - discovered Docker CLI with fixed safe arguments.
            [executable, *arguments], capture_output=True, text=True, check=False, timeout=20
        )
        if result.returncode:
            raise ChatwootSetupError(category)
        if arguments[0] == "info" and result.stdout.strip() != "linux":
            raise ChatwootSetupError("chatwoot_linux_host_network_required")
    return executable


def validate_resource_ownership(resource: dict[str, Any], owner: str) -> None:
    """Require both our Compose project and a private installation-specific ownership label."""
    labels = resource.get("Labels")
    if labels is None and isinstance(resource.get("Config"), dict):
        labels = resource["Config"].get("Labels")
    if (
        not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != PROJECT
        or not owner
        or labels.get(OWNER_LABEL) != owner
    ):
        raise ChatwootSetupError("chatwoot_setup_unowned")


def _inspect_resources(docker: str, owner: str) -> bool:
    """Refuse adoption of existing project containers or any reserved volume name."""

    def query(arguments: list[str]) -> str:
        """Read bounded daemon metadata while suppressing raw diagnostics."""
        result = subprocess.run(  # noqa: S603 - fixed Docker queries; never print daemon output.
            [docker, *arguments], capture_output=True, text=True, check=False, timeout=20
        )
        if result.returncode:
            raise ChatwootSetupError("chatwoot_docker_inspection_failed")
        return result.stdout

    ids = query(["ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"]).split()
    if ids:
        resources = json.loads(query(["inspect", *ids]))
        if not isinstance(resources, list) or not all(isinstance(item, dict) for item in resources):
            raise ChatwootSetupError("chatwoot_docker_inspection_failed")
        for resource in resources:
            validate_resource_ownership(resource, owner)
    volumes = query(["volume", "ls", "--format", "{{.Name}}"]).splitlines()
    reserved = {f"{PROJECT}_{name}" for name in ("postgres_data", "redis_data", "storage_data")}
    owned_volumes = [name for name in volumes if name in reserved]
    if owned_volumes:
        resources = json.loads(query(["volume", "inspect", *owned_volumes]))
        if not isinstance(resources, list) or not all(isinstance(item, dict) for item in resources):
            raise ChatwootSetupError("chatwoot_docker_inspection_failed")
        for resource in resources:
            validate_resource_ownership(resource, owner)
    return bool(ids or owned_volumes)


def _compose(docker: str, root: Path) -> list[str]:
    """Build a Compose invocation scoped to the fixed project and private environment."""
    return [
        docker,
        "compose",
        "--project-name",
        PROJECT,
        "--env-file",
        str(root / "compose.env"),
        "--file",
        str(COMPOSE_FILE),
    ]


def _run_private(command: list[str], root: Path, *, timeout: int = 1200) -> str:
    """Capture subprocess diagnostics privately; expose only a safe category on failure."""
    log = root / "setup.log"
    if log.is_symlink():
        raise ChatwootSetupError("chatwoot_setup_unowned")
    descriptor = os.open(
        log, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "ab") as output:
        if hasattr(os, "fchmod"):
            os.fchmod(output.fileno(), 0o600)
        else:
            log.chmod(0o600)
        start = output.seek(0, os.SEEK_END)
        environment = dict(os.environ)
        for key in dotenv_values(root / "compose.env"):
            environment.pop(key, None)
        for key in tuple(environment):
            if key.startswith("COMPOSE_"):
                environment.pop(key)
        result = subprocess.run(  # noqa: S603 - owned Compose command; secrets are files, not args.
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env=environment,
        )
    if result.returncode:
        raise ChatwootSetupError("chatwoot_compose_failed")
    with log.open("rb") as source:
        source.seek(start)
        return source.read().decode("utf-8", errors="replace")


def _free_ports() -> None:
    """Fail before creating containers if the dedicated loopback listeners are already used."""
    for port in (3000, 55433, 6380):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                raise ChatwootSetupError("chatwoot_loopback_port_in_use") from None


def _provision(docker: str, root: Path) -> dict[str, Any]:
    """Run official Rails preparation and one transactionally guarded application bootstrap."""
    command = _compose(docker, root)
    _run_private([*command, "up", "-d", "--wait", "postgres", "redis"], root)
    _run_private(
        [*command, "run", "--rm", "rails", "bundle", "exec", "rails", "db:chatwoot_prepare"], root
    )
    runner = [
        *command,
        "run",
        "--rm",
        "rails",
        "bundle",
        "exec",
        "rails",
        "runner",
        "/run/veritycx/provision.rb",
    ]
    # setup.log may include sensitive Rails diagnostics; it is never echoed or attached.
    content = _run_private(runner, root)
    lines = [
        line.removeprefix("VERITYCX_RESULT=")
        for line in content.splitlines()
        if line.startswith("VERITYCX_RESULT=")
    ]
    if not lines:
        raise ChatwootSetupError("chatwoot_provision_result_invalid")
    result = json.loads(lines[-1])
    if not isinstance(result, dict):
        raise ChatwootSetupError("chatwoot_provision_result_invalid")
    _validate_result(result)
    _write_private(root / "integration.json", json.dumps(result, sort_keys=True) + "\n")
    _run_private([*command, "up", "-d", "--wait", "rails", "sidekiq"], root)
    return dict(result)


def _check(docker: str, root: Path) -> str:
    """Inspect setup without repairing permissions, generating secrets or starting services."""
    marker = _validate_root(root)
    _inspect_resources(docker, str(marker["owner"]) if marker else "")
    if marker is None:
        return "chatwoot_setup_missing"
    _credentials(root, marker)
    if not (root / "compose.env").is_file() or not (root / "integration.json").is_file():
        return "chatwoot_setup_incomplete"
    result = _read_json(root / "integration.json")
    values = _application_values(result)
    try:
        path = PROJECT_ROOT / ".env"
        if not path.is_file() or _app_environment_content(path, values) != path.read_text():
            return "chatwoot_setup_incomplete"
    except LocalSetupError:
        raise ChatwootSetupError("chatwoot_app_configuration_conflict") from None
    status = subprocess.run(  # noqa: S603 - fixed project Compose inspection.
        [*_compose(docker, root), "ps", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if status.returncode:
        raise ChatwootSetupError("chatwoot_docker_inspection_failed")
    # Compose emits one JSON object per line (some releases return a JSON list).
    parsed = [json.loads(line) for line in status.stdout.splitlines() if line.strip()]
    services = parsed[0] if len(parsed) == 1 and isinstance(parsed[0], list) else parsed
    if not all(isinstance(item, dict) for item in services):
        raise ChatwootSetupError("chatwoot_docker_inspection_failed")
    active = {
        item.get("Service")
        for item in services
        if item.get("State") == "running"
        and (item.get("Service") == "sidekiq" or item.get("Health") == "healthy")
    }
    return (
        "chatwoot_setup_ready"
        if active == {"rails", "sidekiq", "postgres", "redis"}
        else "chatwoot_setup_stopped"
    )


def main() -> int:
    """Prepare private configuration, inspect it, or provision the owned local deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only runtime and setup inspection")
    mode.add_argument(
        "--prepare", action="store_true", help="generate private local files without Docker"
    )
    parser.add_argument(
        "--allow-local-webhooks",
        action="store_true",
        help="explicitly allow private-network fetches inside local Chatwoot only",
    )
    arguments = parser.parse_args()
    root = arguments.root.absolute()
    try:
        if arguments.prepare:
            if not arguments.allow_local_webhooks:
                raise ChatwootSetupError("chatwoot_local_webhooks_opt_in_required")
            _prepare(root)
            print("chatwoot_setup_prepared")
        else:
            docker = _docker()
            if arguments.check:
                status = _check(docker, root)
                print(status)
                return 0 if status == "chatwoot_setup_ready" else 1
            if not arguments.allow_local_webhooks:
                raise ChatwootSetupError("chatwoot_local_webhooks_opt_in_required")
            marker = _validate_root(root)
            existing = _inspect_resources(docker, str(marker["owner"]) if marker else "")
            if not existing:
                _free_ports()
            _prepare(root)
            result = _provision(docker, root)
            write_application_environment(PROJECT_ROOT / ".env", result)
            try:
                _run_private(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "scripts" / "manage_support.py"),
                        "db",
                        "migrate",
                    ],
                    root,
                )
            except ChatwootSetupError:
                raise ChatwootSetupError("chatwoot_application_migration_failed") from None
            print("chatwoot_setup_ready")
        print(f"private_directory={root}")
        return 0
    except ChatwootSetupError as error:
        print(str(error))
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print("chatwoot_setup_failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
