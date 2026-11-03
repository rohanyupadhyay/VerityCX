"""Run the standalone comparison without credentials or reachable storage."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Make accidental SDK/storage dependencies fail while leaving source resources real."""
    env = dict(
        os.environ,
        OPENAI_API_KEY="",
        VERITYCX_DATABASE_URL="host=127.0.0.1 port=1 dbname=unavailable user=none",
        VERITYCX_TEST_DATABASE_URL="",
        LANGSMITH_API_KEY="KEY_CANARY",
    )
    return subprocess.run(  # noqa: S603 - authored CLI arguments.
        [sys.executable, "scripts/compare_retrieval.py", *arguments],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_real_cli_compares_original_cards_and_writes_new_markdown(tmp_path: Path) -> None:
    """The public command must execute real selectors and preserve report content boundaries."""
    path = tmp_path / "comparison.md"
    result = run_cli(
        "--case", "broad-cards-original", "--repetitions", "1", "--markdown", str(path)
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["passed"] and len(data["rows"]) == 6
    assert data["provider_requests"] == 0 and data["cost"] is None
    assert any(
        r["version"] == "v1" and r["metrics"]["contract_passed"] is False for r in data["rows"]
    )
    current = next(r for r in data["rows"] if r["version"] == "v3" and r["track"] == "raw")
    assert set(current["selected_document_ids"]) == {"policy-03", "policy-08", "policy-16"}
    assert all(
        word not in result.stdout + result.stderr
        for word in ("KEY_CANARY", "What cards does", "fictional portfolio demonstration")
    )
    report = path.read_text()
    assert "not held-out" in report and "shared" in report
    assert "broad-cards-original" in report and "v1" in report and "v3" in report
    assert data["provenance"]["fixture_sha256"] in report
    first = path.read_bytes()
    again = run_cli("--case", "broad-cards-original", "--markdown", str(path))
    assert again.returncode == 1 and path.read_bytes() == first
    assert again.stdout.strip() == "comparison_report_exists"


@pytest.mark.parametrize(
    "arguments,category",
    [
        (["--case", "KEY_CANARY"], "invalid_regression_selection"),
        (
            ["--case", "broad-cards-original", "--case", "broad-cards-original"],
            "invalid_regression_selection",
        ),
        (["--repetitions", "0"], "invalid_comparison_repetitions"),
        (["--repetitions", "21"], "invalid_comparison_repetitions"),
        (["--repetitions", "KEY_CANARY"], "invalid_comparison_repetitions"),
        (["--live"], "invalid_comparison_arguments"),
    ],
)
def test_invalid_cli_inputs_fail_without_raw_values(arguments: list[str], category: str) -> None:
    """Bad selections/budgets cannot reach providers, duplicate data or leak arguments."""
    result = run_cli(*arguments)
    assert result.returncode != 0
    assert category in result.stdout + result.stderr
    assert "KEY_CANARY" not in result.stdout + result.stderr


def test_current_execution_failure_has_nonzero_exit_and_private_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed current selector must not become a successful baseline-comparison command."""
    import scripts.compare_retrieval as command

    import veritycx.service.retrieval_comparison as comparison

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("PRIVATE_ERROR_CANARY")

    monkeypatch.setattr(comparison, "select_scoped_evidence", fail)
    assert command.main(["--case", "broad-cards-original", "--repetitions", "1"]) == 1
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert not data["passed"] and len(data["rows"]) == 6
    assert "PRIVATE_ERROR_CANARY" not in output.out + output.err


def test_renderer_preserves_unknown_and_error_distinctions() -> None:
    """Unknown precision must remain unmeasured rather than becoming zero or perfect."""
    from veritycx.service.retrieval_comparison import compare_retrieval
    from veritycx.service.retrieval_comparison_report import render_markdown

    report = compare_retrieval(case_ids=["unsupported-business"], repetitions=1)
    text = render_markdown(report)
    assert "—" in text and "unassessed" in text and "not answer correctness" in text


def test_report_preflight_os_error_cannot_escape_as_a_raw_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An inaccessible explicit destination must fail before benchmarking without path contents."""
    import scripts.compare_retrieval as command

    original_exists = Path.exists

    def fail(path: Path) -> bool:
        if path.name == "private.md":
            raise PermissionError("KEY_CANARY")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fail)
    assert command.main(["--markdown", "private.md"]) == 1
    output = capsys.readouterr()
    assert output.out.strip() == "retrieval_comparison_failed"
    assert "KEY_CANARY" not in output.out + output.err


@pytest.mark.parametrize(
    "arguments",
    [
        ["--unknown", "KEY_CANARY"],
        ["QUESTION_CANARY POLICY_BODY_CANARY"],
        ["--case", "broad-cards-original", "--oops=KEY_CANARY"],
    ],
)
def test_parser_failures_never_echo_unexpected_content(arguments: list[str]) -> None:
    """Unknown flags and positional content must fail with a finite content-free category."""
    result = run_cli(*arguments)
    assert result.returncode == 2
    assert result.stderr.strip() == "invalid_comparison_arguments"
    assert not result.stdout
    assert "CANARY" not in result.stdout + result.stderr


def test_parser_help_remains_available_without_benchmark_execution() -> None:
    """Sanitizing parser errors must preserve the ordinary successful help path."""
    result = run_cli("--help")
    assert result.returncode == 0 and "--repetitions" in result.stdout
    assert "retrieval-comparison" not in result.stdout and not result.stderr
