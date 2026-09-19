"""Guard dedicated test connections and subprocess ownership without destructive resets."""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict


class RedactedDsn(str):
    """Keep connection strings out of pytest argument representations."""

    def __repr__(self) -> str:
        """Return a fixed diagnostic label instead of the secret-bearing connection string."""
        return "<dedicated-test-dsn>"


def require_test_database(dsn: str) -> str:
    """Validate an explicit loopback test DSN, returning it without logging secrets."""
    try:
        fields = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError("dedicated_test_database_required") from None
    allowed = {"host", "port", "dbname", "user", "password", "connect_timeout", "sslmode"}
    if (
        not dsn
        or set(fields) - allowed
        or fields.get("dbname") != "veritycx_support_test"
        or fields.get("host") not in {"127.0.0.1", "::1"}
        or not fields.get("user")
    ):
        raise ValueError("dedicated_test_database_required")
    return RedactedDsn(dsn)


class OwnedProcesses:
    """Hold actual child handles; never accept arbitrary PIDs for cleanup."""

    def __init__(self) -> None:
        """Start with no authority to stop any process."""
        self._children: list[subprocess.Popen[bytes]] = []

    def start(
        self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str]
    ) -> subprocess.Popen[bytes]:
        """Launch an explicit argument vector without a shell and retain its handle."""
        child = subprocess.Popen(  # noqa: S603 - caller is trusted test code; never HTTP input.
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._children.append(child)
        return child

    def stop(self, child: subprocess.Popen[bytes]) -> None:
        """Stop only a retained handle; wait and escalate if graceful exit times out."""
        if not any(owned is child for owned in self._children):
            raise ValueError("unowned_process")
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        self._children.remove(child)

    def close(self) -> None:
        """Reap all remaining owned children after a test, including failure paths."""
        for child in tuple(self._children):
            self.stop(child)
