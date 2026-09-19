"""Reject validation against unrelated storage before launching any child processes."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "dsn", ["", "host=127.0.0.1 dbname=postgres", "host=127.0.0.1 dbname=veritycx_support"]
)
def test_validation_refuses_unsafe_database(dsn: str) -> None:
    """Offline validation requires its explicit dedicated test database identity."""
    env = dict(os.environ, VERITYCX_TEST_DATABASE_URL=dsn)
    result = subprocess.run(
        [sys.executable, "scripts/validate_support.py", "--suite", "offline"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "dedicated_test_database_required"
    assert "Traceback" not in result.stderr


def test_driver_refuses_unowned_process() -> None:
    """The actual validation driver must not terminate a handle created elsewhere."""
    from veritycx.service.validation import ProcessOwner, ValidationError

    process = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        with pytest.raises(ValidationError, match="unowned_process"):
            ProcessOwner(dict(os.environ)).stop(process)
    finally:
        process.wait(timeout=10)


@pytest.mark.parametrize("suite", ["grounding", "demo"])
def test_live_validation_requires_opt_in(suite: str) -> None:
    """Paid suites must refuse execution before reading credentials or starting children."""
    # The parametrized suite is a fixed authored test value, never external input.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/validate_support.py", "--suite", suite],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "live_opt_in_required"


def test_live_preflight_missing_credentials() -> None:
    """Validated local test storage does not authorize an implicit paid provider fallback."""
    from veritycx.service.validation import ValidationError, live_preflight

    with pytest.raises(ValidationError, match="missing_provider_credential"):
        live_preflight(
            {
                "VERITYCX_TEST_DATABASE_URL": (
                    "host=127.0.0.1 dbname=veritycx_support_test user=fixture"
                )
            },
            live=True,
        )
