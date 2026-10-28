"""Build and run the customer page, API and worker through one owned local supervisor."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import httpx

from veritycx import PROJECT_ROOT
from veritycx.environment import EnvironmentLoadError, load_project_environment
from veritycx.knowledge.configuration import active_corpus
from veritycx.policy.sources import SourceError
from veritycx.service.auth import AuthError, load_principals
from veritycx.service.configuration import ConfigurationError, load_configuration

LOCAL = PROJECT_ROOT / ".cache" / "support" / "local"


class LaunchError(ValueError):
    """Report a content-free startup category with details retained in private local logs."""


class LocalProcesses:
    """Retain child handles and private logs so shutdown cannot target unrelated services."""

    def __init__(self, directory: Path) -> None:
        """Select a private log directory and start with no child ownership."""
        self.directory = directory
        self.children: list[subprocess.Popen[bytes]] = []

    def start(self, label: str, command: Sequence[str]) -> subprocess.Popen[bytes]:
        """Start a fixed local command without a shell, retaining its handle for cleanup."""
        self.directory.mkdir(parents=True, exist_ok=True)
        log_path = self.directory / f"{label}.log"
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        log_path.chmod(0o600)
        with os.fdopen(descriptor, "ab") as output:
            child = subprocess.Popen(  # noqa: S603 - fixed launcher-owned argument vectors.
                command,
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
        self.children.append(child)
        return child

    def close(self) -> None:
        """Terminate and reap only children started by this supervisor, safely on repeat."""
        for child in self.children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        self.children.clear()


def port_available(host: str, port: int) -> bool:
    """Check whether the requested local listener can be bound without disturbing services."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family) as listener:
        try:
            listener.bind((host, port))
        except OSError:
            return False
    return True


def _build_frontend() -> None:
    """Install locked frontend dependencies when absent and retain build diagnostics privately."""
    npm = shutil.which("npm")
    if npm is None:
        raise LaunchError("frontend_node_required")
    LOCAL.mkdir(parents=True, exist_ok=True)
    log = LOCAL / "frontend-build.log"
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    log.chmod(0o600)
    commands = [[npm, "run", "build"]]
    if not (PROJECT_ROOT / "node_modules").is_dir():
        commands.insert(0, [npm, "ci"])
    with os.fdopen(descriptor, "ab") as output:
        for command in commands:
            result = subprocess.run(  # noqa: S603 - fixed npm commands, no shell.
                command,
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode:
                raise LaunchError("frontend_build_failed")


def _wait_ready(base_url: str, processes: LocalProcesses) -> None:
    """Wait for actual API/worker readiness, never probing the paid AI provider."""
    deadline = time.monotonic() + 30
    with httpx.Client(timeout=3, trust_env=False) as client:
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in processes.children):
                raise LaunchError("support_process_exited")
            try:
                response = client.get(base_url + "/health/ready")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
    raise LaunchError("support_readiness_timeout")


def main() -> int:
    """Optionally prepare/build, then supervise the API and worker until interrupted."""
    parser = argparse.ArgumentParser(description="Run the VerityCX customer support app")
    parser.add_argument("--provider", choices=["deterministic", "openai"])
    parser.add_argument("--build", action="store_true", help="rebuild the customer frontend")
    parser.add_argument(
        "--setup", action="store_true", help="run maintained local app bootstrap first"
    )
    arguments = parser.parse_args()
    processes = LocalProcesses(LOCAL)
    try:
        if arguments.setup:
            result = subprocess.run(  # noqa: S603 - existing fixed project command.
                [sys.executable, str(PROJECT_ROOT / "scripts" / "setup_support_local.py"), "--app"],
                cwd=PROJECT_ROOT,
                check=False,
            )
            if result.returncode:
                raise LaunchError("support_setup_failed")
        load_project_environment()
        configuration = load_configuration(
            Path("config/support.toml"),
            os.environ,
            provider=arguments.provider,
        )
        load_principals(configuration.auth_file)
        active_corpus(configuration.settings.corpus_mode)
        if not port_available(configuration.settings.bind, configuration.settings.port):
            raise LaunchError("support_port_in_use")
        if arguments.build or not (PROJECT_ROOT / "dist" / "chat" / "index.html").is_file():
            _build_frontend()
        provider = configuration.settings.provider
        processes.start(
            "api", [sys.executable, "-m", "veritycx.service.main", "--provider", provider]
        )
        processes.start(
            "worker",
            [sys.executable, "-m", "veritycx.orchestration.worker", "--provider", provider],
        )
        host = configuration.settings.bind
        base_url = (
            f"http://{'[' + host + ']' if ':' in host else host}:{configuration.settings.port}"
        )
        _wait_ready(base_url, processes)
        print(f"support_ready: {base_url}", flush=True)
        print("service_logs: .cache/support/local/", flush=True)
        while all(child.poll() is None for child in processes.children):
            time.sleep(0.5)
        raise LaunchError("support_process_exited")
    except (LaunchError, ConfigurationError, EnvironmentLoadError, AuthError, SourceError) as error:
        print(str(error), flush=True)
        return 1
    except OSError:
        print("support_launch_failed", flush=True)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        processes.close()


if __name__ == "__main__":
    raise SystemExit(main())
