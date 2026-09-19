"""Verify test infrastructure refuses unrelated databases and process handles."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.harness import OwnedProcesses, require_test_database


@pytest.mark.parametrize(
    "dsn",
    [
        "",
        "dbname=postgres",
        "dbname=veritycx_support",
        "dbname=veritycx_support_test host=example.com",
        "host=127.0.0.1 dbname=veritycx_support_test options=-csearch_path=public",
    ],
)
def test_reject_database(dsn: str) -> None:
    """Reject absent, unrelated, remote or option-bearing test connections."""
    with pytest.raises(ValueError, match="dedicated_test_database_required"):
        require_test_database(dsn)


def test_accept_database() -> None:
    """Accept only the dedicated loopback database name."""
    dsn = "host=127.0.0.1 dbname=veritycx_support_test user=veritycx_support"
    assert require_test_database(dsn) == dsn


def test_refuse_unowned_process() -> None:
    """A process created elsewhere must not be terminated by the harness."""
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        with pytest.raises(ValueError, match="unowned_process"):
            OwnedProcesses().stop(process)
    finally:
        process.wait(timeout=10)


def test_owned_child_cleanup(tmp_path: Path) -> None:
    """Only launched children can be stopped, and cleanup removes their authority."""
    owned = OwnedProcesses()
    child = owned.start(
        [sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, env=os.environ
    )
    owned.close()
    assert child.poll() is not None
    with pytest.raises(ValueError, match="unowned_process"):
        owned.stop(child)
