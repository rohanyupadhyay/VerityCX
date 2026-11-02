"""Isolate explicit retrieval validation to an owned test-only child process."""

import argparse
import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence

from openai import AsyncOpenAI

from veritycx import PROJECT_ROOT
from veritycx.knowledge.configuration import active_corpus, source_mode
from veritycx.knowledge.manifest import approve, prepare
from veritycx.persistence.database import database_pool
from veritycx.service.configuration import Settings
from veritycx.service.retrieval_cases import RegressionError, load_cases, load_replays, select_cases
from veritycx.service.retrieval_providers import live_provider_factory, replay_provider_factory
from veritycx.service.retrieval_reports import (
    PublicSummary,
    exit_status,
    public_summary,
    write_review_report,
)
from veritycx.service.retrieval_runner import exercise_regressions
from veritycx.service.runtime import run_async
from veritycx.service.validation import dedicated_database, live_preflight


def _child_environment(env: Mapping[str, str], *, live: bool) -> dict[str, str]:
    """Keep runtime identity test-only while removing integration/admin/tracing secrets."""
    dsn = dedicated_database(env.get("VERITYCX_TEST_DATABASE_URL", ""))
    child = {
        name: value
        for name, value in env.items()
        if name
        not in {
            "VERITYCX_MIGRATION_DATABASE_URL",
            "VERITYCX_TEST_MIGRATION_DATABASE_URL",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
        }
        and not name.startswith(("VERITYCX_CHATWOOT", "CHATWOOT_"))
    }
    if not live:
        child.pop("OPENAI_API_KEY", None)
    child.update(
        VERITYCX_DATABASE_URL=dsn,
        VERITYCX_TEST_DATABASE_URL=dsn,
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    return child


def _stop(child: subprocess.Popen[str]) -> None:
    """Terminate and reap only this invocation's still-running child."""
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def run_regressions(
    env: Mapping[str, str], *, live: bool = False, case_ids: Sequence[str] | None = None
) -> dict[str, object]:
    """Validate intent before spawning; publish only a complete validated child summary."""
    cases = select_cases(load_cases(), case_ids)
    if live:
        live_preflight(dict(env), live=True)
    child_env = _child_environment(env, live=live)
    command = [sys.executable, "-m", "veritycx.service.retrieval_command", "--child"]
    if live:
        command.append("--live")
    for case in cases:
        command.extend(("--case", case.id))
    try:
        child = subprocess.Popen(  # noqa: S603 - fixed module and validated catalog IDs.
            command,
            cwd=PROJECT_ROOT,
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        raise RegressionError("regression_child_unavailable") from None
    try:
        output, _ = child.communicate(timeout=60 + 60 * sum(len(case.turns) for case in cases))
    except subprocess.TimeoutExpired:
        raise RegressionError("regression_execution_timeout") from None
    finally:
        _stop(child)
    try:
        if len(output) > 131072:
            raise ValueError("oversized_summary")
        summary = PublicSummary.model_validate_json(output)
        expected = [(case.id, [turn.id for turn in case.turns]) for case in cases]
        observed = [
            (case.case_id, [turn.turn_id for turn in case.turns]) for case in summary.scenarios
        ]
        data = summary.model_dump(mode="json")
        if (
            observed != expected
            or summary.mode != ("live" if live else "offline")
            or child.returncode != exit_status(data)
        ):
            raise ValueError("incomplete_summary")
        return data
    except ValueError:
        raise RegressionError("invalid_regression_response") from None


async def _exercise_child(*, live: bool, case_ids: Sequence[str] | None) -> dict[str, object]:
    """Use only explicit inherited child configuration; never reload root dotenv."""
    env = dict(os.environ)
    dsn = dedicated_database(env.get("VERITYCX_DATABASE_URL", ""))
    if live:
        live_preflight(env, live=True)
    cases = load_cases()
    selected = select_cases(cases, case_ids)
    root, cache, pin = source_mode("synthetic", validation=True)
    manifest = prepare(root, cache, "synthetic", pin)
    approve(root, cache, manifest.aggregate_hash)
    manifest, evidence = active_corpus("synthetic", validation=True)
    with (PROJECT_ROOT / "config/support.toml").open("rb") as source:
        values = tomllib.load(source)
    settings = Settings.model_validate(
        {
            **values,
            "provider": "openai" if live else "deterministic",
            "corpus_mode": "synthetic",
            "traces_enabled": False,
        }
    )
    async with database_pool(dsn, max_size=settings.pool_max_size) as pool:
        if live:
            async with AsyncOpenAI(api_key=env["OPENAI_API_KEY"], max_retries=0) as client:
                run = await exercise_regressions(
                    pool,
                    settings,
                    selected,
                    manifest=manifest,
                    evidence=evidence,
                    providers=live_provider_factory(client, settings),
                    mode="live",
                )
        else:
            run = await exercise_regressions(
                pool,
                settings,
                selected,
                manifest=manifest,
                evidence=evidence,
                providers=replay_provider_factory(load_replays(cases, manifest)),
                mode="offline",
            )
    write_review_report(run)
    return public_summary(run)


def main() -> int:
    """Expose only a fixed internal child protocol; the maintained script is the user entry."""
    parser = argparse.ArgumentParser(description="Owned retrieval regression child")
    parser.add_argument("--child", action="store_true", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    try:
        result = run_async(_exercise_child(live=args.live, case_ids=args.case_ids))
        print(json.dumps(result, sort_keys=True))
        return exit_status(result)
    except Exception:
        print(json.dumps({"error": "regression_execution_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
