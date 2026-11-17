"""Verify the maintained app launcher preserves other listeners and owns child cleanup."""

import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts import setup_support_local


@pytest.mark.parametrize(
    "arguments,provider,key,corpus_mode",
    [
        ([], "openai", "offline-test-no-network", "official"),
        (["--provider", "deterministic"], "deterministic", None, "synthetic"),
        (["--corpus-mode", "synthetic"], "openai", "offline-test-no-network", "synthetic"),
        ([], None, None, "official"),
    ],
)
def test_customer_launcher_uses_live_provider_unless_offline_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    provider: str | None,
    key: str | None,
    corpus_mode: str,
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
    from veritycx.knowledge.manifest import build_manifest
    from veritycx.knowledge.models import CorpusManifest

    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "policy.json").write_text(
        '{"id":"policy-01","title":"Policy","content":"Synthetic fact."}'
    )
    initialized: list[str] = []

    def initialize(mode: str) -> CorpusManifest:
        """Replace external acquisition while retaining a real typed corpus inventory."""
        initialized.append(mode)
        return build_manifest(documents, "synthetic", "synthetic-v1")

    monkeypatch.setattr(run_support, "ensure_corpus", initialize, raising=False)
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
        assert not initialized
        return
    assert run_support.main() == 0
    assert initialized == [corpus_mode]
    assert commands == [
        [sys.executable, "-m", module, "--provider", provider, "--corpus-mode", corpus_mode]
        for module in ("veritycx.service.main", "veritycx.orchestration.worker")
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
    assert "--corpus-mode" in result.stdout


def test_failed_corpus_initialization_starts_no_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The launcher must report initialization failure before publishing either child service."""
    from scripts import run_support

    from veritycx.policy.sources import SourceError
    from veritycx.service.auth import init_demo

    auth, _, _ = init_demo(tmp_path / "auth")
    monkeypatch.setenv("VERITYCX_AUTH_FILE", str(auth))
    monkeypatch.setenv("VERITYCX_DATABASE_URL", "postgresql://offline-test@127.0.0.1/unused")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-no-network")
    monkeypatch.setattr(sys, "argv", ["run_support.py"])
    monkeypatch.setattr(run_support, "load_project_environment", lambda: None)
    monkeypatch.setattr(run_support, "port_available", lambda *_: True)

    def unavailable(mode: str) -> None:
        """Model a real fail-closed source validation result."""
        raise SourceError("corpus_changed")

    def forbidden_start(*args: object, **kwargs: object) -> None:
        """Any service publication after failed initialization is a contract violation."""
        pytest.fail("service started before corpus initialization succeeded")

    monkeypatch.setattr(run_support, "ensure_corpus", unavailable, raising=False)
    monkeypatch.setattr(run_support.LocalProcesses, "start", forbidden_start)
    assert run_support.main() == 1
    assert "corpus_changed" in capsys.readouterr().out


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
