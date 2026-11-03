"""Guard explicit live opt-in, test-only execution and sanitized child publication."""

import json
import os
import subprocess
import sys

import pytest

from tests.support.unit.test_retrieval_reports import sample_run

TEST_DSN = "host=127.0.0.1 dbname=veritycx_support_test user=fixture password=DSN_CANARY"


@pytest.mark.parametrize(
    "arguments,dsn,key,want",
    [
        (
            ["--suite", "retrieval", "--case", "unknown"],
            TEST_DSN,
            "",
            "invalid_regression_selection",
        ),
        (
            [
                "--suite",
                "retrieval",
                "--case",
                "broad-cards-original",
                "--case",
                "broad-cards-original",
            ],
            TEST_DSN,
            "",
            "invalid_regression_selection",
        ),
        (["--suite", "retrieval", "--live"], TEST_DSN, "", "missing_provider_credential"),
        (
            ["--suite", "retrieval"],
            TEST_DSN.replace("veritycx_support_test", "veritycx_support"),
            "",
            "dedicated_test_database_required",
        ),
        (
            ["--suite", "offline", "--case", "broad-cards-original"],
            TEST_DSN,
            "",
            "invalid_case_scope",
        ),
    ],
)
def test_invalid_invocations_fail_before_child_execution(
    arguments: list[str], dsn: str, key: str, want: str
) -> None:
    """Invalid selections and unsafe storage must not reach any provider or child."""
    env = dict(os.environ, VERITYCX_TEST_DATABASE_URL=dsn, OPENAI_API_KEY=key)
    result = subprocess.run(  # noqa: S603 - fixed authored CLI test cases.
        [sys.executable, "scripts/validate_support.py", *arguments],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == want
    assert "CANARY" not in result.stdout + result.stderr


def test_child_environment_is_test_only_and_parent_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inherited app credentials and tracing cannot redirect offline execution."""
    from veritycx.service import retrieval_command
    from veritycx.service.retrieval_reports import public_summary

    before = dict(os.environ)
    observed: list[dict[str, object]] = []
    summary = public_summary(sample_run())

    class Child:
        """Stand in only for the external process boundary, retaining its actual environment."""

        returncode = 0

        def __init__(self, *args: object, **kwargs: object) -> None:
            observed.append(kwargs)

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            return json.dumps(summary), "PRIVATE_CHILD_ERROR_CANARY"

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(subprocess, "Popen", Child)
    env = {
        **before,
        "VERITYCX_DATABASE_URL": "host=127.0.0.1 dbname=veritycx_support user=app",
        "VERITYCX_TEST_DATABASE_URL": TEST_DSN,
        "OPENAI_API_KEY": "KEY_CANARY",
        "LANGSMITH_TRACING": "true",
        "LANGCHAIN_API_KEY": "TRACE_CANARY",
        "VERITYCX_MIGRATION_DATABASE_URL": "ADMIN_CANARY",
        "VERITYCX_CHATWOOT_API_TOKEN": "CHATWOOT_CANARY",
        "PGHOSTADDR": "192.0.2.1",
        "PGSERVICE": "external",
        "PGSERVICEFILE": "/private/service.conf",
        "PGOPTIONS": "-c search_path=external",
        "PGPASSFILE": "/private/pgpass",
        "PGDATABASE": "external",
    }
    result = retrieval_command.run_regressions(env, case_ids=["broad-cards-original"])
    assert result["automated_passed"] is True
    assert dict(os.environ) == before
    child_env = observed[0]["env"]
    assert isinstance(child_env, dict)
    assert child_env["VERITYCX_DATABASE_URL"] == TEST_DSN
    assert child_env["LANGSMITH_TRACING"] == "false"
    assert not any(name.startswith("PG") for name in child_env)
    assert env["PGHOSTADDR"] == "192.0.2.1"
    assert not any(
        "CANARY" in str(value)
        for name, value in child_env.items()
        if name != "VERITYCX_DATABASE_URL" and name != "VERITYCX_TEST_DATABASE_URL"
    )


def test_parent_rejects_private_or_incomplete_child_summaries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A raw child message or silently dropped scenario must never become public success."""
    from veritycx.service import retrieval_command
    from veritycx.service.retrieval_reports import public_summary

    summary = public_summary(sample_run())
    payloads = [
        "QUESTION_CANARY",
        json.dumps({**summary, "question": "QUESTION_CANARY"}),
        json.dumps(summary),
    ]

    class Child:
        """Return controlled protocol violations without starting a process."""

        returncode = 0

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            return payloads.pop(0), "EXCEPTION_CANARY"

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(subprocess, "Popen", Child)
    for ids in (["broad-cards-original"], ["broad-cards-original"], None):
        with pytest.raises(ValueError):
            retrieval_command.run_regressions(
                {"VERITYCX_TEST_DATABASE_URL": TEST_DSN}, case_ids=ids
            )
    assert capsys.readouterr().out == ""


def test_interruption_terminates_only_the_owned_child(monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted parent cannot leak its validation process or kill unrelated work."""
    from veritycx.service import retrieval_command

    stopped = []

    class Child:
        """Expose just the lifecycle of the one process created by this invocation."""

        returncode: int | None = None

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            raise KeyboardInterrupt

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            stopped.append("owned")
            self.returncode = -15

        def wait(self, timeout: float | None = None) -> int:
            return -15

    monkeypatch.setattr(subprocess, "Popen", Child)
    with pytest.raises(KeyboardInterrupt):
        retrieval_command.run_regressions(
            {"VERITYCX_TEST_DATABASE_URL": TEST_DSN}, case_ids=["broad-cards-original"]
        )
    assert stopped == ["owned"]


def test_child_start_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    """An operating-system startup error must not publish raw exception details."""
    from veritycx.service import retrieval_command

    def fail(*args: object, **kwargs: object) -> None:
        """Fail at the real process-start boundary with a private canary."""
        raise OSError("KEY_CANARY")

    monkeypatch.setattr(subprocess, "Popen", fail)
    with pytest.raises(ValueError, match="regression_child_unavailable"):
        retrieval_command.run_regressions(
            {"VERITYCX_TEST_DATABASE_URL": TEST_DSN}, case_ids=["broad-cards-original"]
        )
