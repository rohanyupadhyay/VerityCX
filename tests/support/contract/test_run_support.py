"""Verify the maintained app launcher preserves other listeners and owns child cleanup."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import setup_support_local


def test_run_command_documents_provider_and_build_options() -> None:
    """Users must be able to discover live-provider startup without knowing module names."""
    result = subprocess.run(
        [sys.executable, "scripts/run_support.py", "--help"],
        cwd=setup_support_local.PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--provider" in result.stdout
    assert "--build" in result.stdout
    assert "--setup" in result.stdout


def test_run_command_refuses_an_existing_listener(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup must preserve an existing service instead of killing it or launching duplicates."""
    from scripts import run_support

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert run_support.port_available("127.0.0.1", port) is False
        assert listener.fileno() >= 0


def test_launcher_stops_only_children_it_started(tmp_path: Path) -> None:
    """Supervisor shutdown must reap retained child handles and leave unrelated processes alone."""
    from scripts import run_support

    owner = run_support.LocalProcesses(tmp_path)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    child = owner.start("synthetic", [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        owner.close()
        assert child.poll() is not None
        assert unrelated.poll() is None
    finally:
        owner.close()
        unrelated.terminate()
        unrelated.wait(timeout=10)
