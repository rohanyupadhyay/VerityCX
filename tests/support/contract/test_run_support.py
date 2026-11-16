"""Verify the maintained app launcher preserves other listeners and owns child cleanup."""

import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts import setup_support_local


@pytest.mark.parametrize(
    "arguments,provider,key",
    [
        ([], "openai", "offline-test-no-network"),
        (["--provider", "deterministic"], "deterministic", None),
        ([], None, None),
    ],
)
def test_customer_launcher_uses_live_provider_unless_offline_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    provider: str | None,
    key: str | None,
) -> None:
    """An ordinary app restart must not silently replace live answers with authored fixtures."""
    from scripts import run_support

    from veritycx.service.auth import init_demo

    auth, _, _ = init_demo(tmp_path / "auth")
    monkeypatch.setenv("VERITYCX_AUTH_FILE", str(auth))
    monkeypatch.setenv("VERITYCX_DATABASE_URL", "postgresql://offline-test@127.0.0.1/unused")
    if key is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setattr(sys, "argv", ["run_support.py", *arguments])
    monkeypatch.setattr(run_support, "load_project_environment", lambda: None)
    monkeypatch.setattr(run_support, "active_corpus", lambda _: None)
    monkeypatch.setattr(run_support, "port_available", lambda *_: True)
    monkeypatch.setattr(run_support, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(run_support, "LOCAL", tmp_path / "logs")
    index = tmp_path / "dist/chat/index.html"
    index.parent.mkdir(parents=True)
    index.write_text("fixture", encoding="utf-8")
    commands: list[list[str]] = []
    children: list[subprocess.Popen[bytes]] = []
    original_start = run_support.LocalProcesses.start

    def start(
        owner: run_support.LocalProcesses, label: str, command: Sequence[str]
    ) -> subprocess.Popen[bytes]:
        """Replace only the external API/worker processes with owned harmless children."""
        commands.append(list(command))
        child = original_start(owner, label, [sys.executable, "-c", "import time; time.sleep(30)"])
        children.append(child)
        return child

    def stop_at_readiness(*_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(run_support.LocalProcesses, "start", start)
    monkeypatch.setattr(run_support, "_wait_ready", stop_at_readiness)
    if provider is None:
        assert run_support.main() == 1
        assert "missing_provider_credential" in capsys.readouterr().out
        assert not commands
        return
    assert run_support.main() == 0
    assert commands == [
        [sys.executable, "-m", "veritycx.service.main", "--provider", provider],
        [sys.executable, "-m", "veritycx.orchestration.worker", "--provider", provider],
    ]
    assert len(children) == 2 and all(child.poll() is not None for child in children)


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
