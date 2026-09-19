"""Own isolated API/worker child handles and validate synthetic HTTP workflows safely."""

import asyncio
import json
import math
import os
import platform
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
import psycopg
import uvicorn
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr

from veritycx.conversations.models import AcceptanceResponse, ConversationView, CreateResponse
from veritycx.knowledge.configuration import active_corpus, source_mode
from veritycx.knowledge.manifest import approve, prepare
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.deterministic import DeterministicProvider, fixture_cases
from veritycx.providers.protocol import ProviderRequest, ProviderResult
from veritycx.service.app import create_app
from veritycx.service.auth import init_demo, load_principals
from veritycx.service.configuration import PROJECT_ROOT, Settings, load_configuration
from veritycx.service.runtime import run_async


class ValidationError(ValueError):
    """Expose only a safe validation category; raw HTTP bodies never become evidence."""


def dedicated_database(dsn: str) -> str:
    """Refuse nonlocal/default databases and connection option injection before spawning."""
    try:
        fields = conninfo_to_dict(dsn)
    except Exception:
        raise ValidationError("dedicated_test_database_required") from None
    allowed = {"host", "port", "dbname", "user", "password", "connect_timeout", "sslmode"}
    if (
        set(fields) - allowed
        or fields.get("dbname") != "veritycx_support_test"
        or fields.get("host") not in {"127.0.0.1", "::1"}
        or not fields.get("user")
    ):
        raise ValidationError("dedicated_test_database_required")
    return dsn


class ProcessOwner:
    """Retain direct subprocess handles; reject cleanup of unowned processes."""

    def __init__(self, env: dict[str, str]) -> None:
        """Capture the child environment without logging any secret values."""
        self.env = env
        self.children: list[subprocess.Popen[bytes]] = []

    def launch(self, arguments: list[str]) -> subprocess.Popen[bytes]:
        """Launch fixed Python entry points with no shell or visible helper window."""
        process = subprocess.Popen(  # noqa: S603 - only internal Python argument vectors reach this API.
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.children.append(process)
        return process

    def stop(self, process: subprocess.Popen[bytes]) -> None:
        """Terminate only an owned handle and reap it before releasing ownership."""
        if not any(item is process for item in self.children):
            raise ValidationError("unowned_process")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        self.children.remove(process)

    def close(self) -> None:
        """Clean up all owned children on success or failure."""
        for process in tuple(self.children):
            self.stop(process)


def serve_test(port: int) -> None:
    """Start an isolated validation API on a selected loopback port using explicit test storage."""
    dedicated_database(os.environ.get("VERITYCX_DATABASE_URL", ""))
    configuration = load_configuration(
        Path("config/support.toml"),
        os.environ,
        provider=os.environ.get("VERITYCX_VALIDATION_PROVIDER", "deterministic"),
        corpus_mode=os.environ.get("VERITYCX_VALIDATION_CORPUS", "synthetic"),
    )
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(configuration),
            host="127.0.0.1",
            port=port,
            access_log=False,
            log_level="critical",
        )
    )
    run_async(server.serve())


def wait_ready(client: httpx.Client, owner: ProcessOwner) -> None:
    """Wait at most 30 seconds for owned live processes and durable readiness."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in owner.children):
            raise ValidationError("owned_process_exited")
        try:
            if client.get("/health/ready").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise ValidationError("readiness_timeout")


def poll_turn(client: httpx.Client, target: str, turn_id: str) -> ConversationView:
    """Wait for one persisted result while retaining response bodies only in memory."""
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        response = client.get(f"/conversations/{target}")
        if response.status_code != 200:
            raise ValidationError("poll_failed")
        view = ConversationView.model_validate_json(response.content)
        if any(
            turn.turn_id == turn_id and turn.status in {"completed", "failed"}
            for turn in view.turns
        ):
            return view
        time.sleep(0.05)
    raise ValidationError("turn_timeout")


def validate_offline(env: dict[str, str]) -> dict[str, int | str]:
    """Run synthetic supported/unsupported/conflicting questions through owned subprocesses."""
    dsn = dedicated_database(env.get("VERITYCX_TEST_DATABASE_URL", ""))
    root, cache, pin = source_mode("synthetic")
    manifest = prepare(root, cache, "synthetic", pin)
    approve(root, cache, manifest.aggregate_hash)
    directory = PROJECT_ROOT / ".cache" / "support" / "validation" / str(uuid4())
    auth, first, _ = init_demo(directory)
    child_env = {
        key: value
        for key, value in env.items()
        if key
        not in {
            "OPENAI_API_KEY",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "VERITYCX_MIGRATION_DATABASE_URL",
            "VERITYCX_TEST_MIGRATION_DATABASE_URL",
        }
    }
    child_env.update(
        VERITYCX_DATABASE_URL=dsn,
        VERITYCX_AUTH_FILE=str(auth),
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    owner = ProcessOwner(child_env)
    try:
        owner.launch(
            ["-c", f"from veritycx.service.validation import serve_test; serve_test({port})"]
        )
        owner.launch(
            [
                "-m",
                "veritycx.orchestration.worker",
                "--provider",
                "deterministic",
                "--corpus-mode",
                "synthetic",
            ]
        )
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=10,
            headers={"Authorization": "Bearer " + first.read_text().strip()},
        ) as client:
            wait_ready(client, owner)
            for case in (fixture_cases()[0], fixture_cases()[20], fixture_cases()[30]):
                created = client.post(
                    "/conversations",
                    json={"schema_version": 1},
                    headers={"Idempotency-Key": str(uuid4())},
                )
                if created.status_code != 201:
                    raise ValidationError("create_failed")
                parent = CreateResponse.model_validate_json(created.content)
                accepted = client.post(
                    f"/conversations/{parent.conversation_id}/turns",
                    json={"schema_version": 1, "message": case.question},
                    headers={"Idempotency-Key": str(uuid4())},
                )
                if accepted.status_code != 202:
                    raise ValidationError("accept_failed")
                turn = AcceptanceResponse.model_validate_json(accepted.content)
                if turn.turn_id is None:
                    raise ValidationError("missing_turn")
                view = poll_turn(client, parent.conversation_id, turn.turn_id)
                result = view.turns[0].result
                if result is None or result.kind != case.disposition:
                    raise ValidationError("unexpected_result")
        return {
            "suite": "offline-knowledge",
            "cases_passed": 3,
            "provider": "deterministic",
            "corpus": manifest.corpus_version,
        }
    finally:
        owner.close()


class PausingProvider:
    """Test-only provider fault hook; no normal worker flag or HTTP input can select it."""

    def __init__(self, sentinel: Path) -> None:
        """Bind the owned validation sentinel path."""
        self.sentinel = sentinel

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Signal after computation but before journal/result commit, then await process death."""
        result = await DeterministicProvider().generate(request)
        self.sentinel.write_text("before_commit", encoding="ascii")
        await asyncio.Event().wait()
        return result


def serve_paused_worker(target: str, sentinel: str) -> None:
    """Run one explicitly targeted test job with an in-memory fault provider."""
    dsn = dedicated_database(os.environ.get("VERITYCX_DATABASE_URL", ""))

    async def exercise() -> None:
        """Claim only the validator's own conversation and use normal fencing/heartbeats."""
        async with database_pool(dsn) as pool:
            repo = Repository(pool)
            worker = uuid4()
            for _ in range(30):
                job = await repo.claim(worker, conversation_id=UUID(target))
                if job is not None:
                    await process_job(pool, job, Settings(), PausingProvider(Path(sentinel)))
                    return
                await asyncio.sleep(1)
        raise ValidationError("claim_timeout")

    run_async(exercise())


def recovery_counts(dsn: str, target: UUID) -> tuple[int, int]:
    """Inspect only row/result counts for the validator-owned conversation."""
    with psycopg.connect(dedicated_database(dsn)) as conn:
        row = conn.execute(
            "SELECT count(*),count(result) FROM support_app.turns WHERE conversation_id=%s",
            (target,),
        ).fetchone()
    if row is None or type(row[0]) is not int or type(row[1]) is not int:
        raise ValidationError("invalid_recovery_counts")
    return row[0], row[1]


def expire_owned_lease(dsn: str, target: UUID, owner_id: UUID) -> None:
    """Advance only an owned test lease to model expiry without changing host time."""
    with psycopg.connect(dedicated_database(dsn)) as conn:
        conn.execute(
            "UPDATE support_app.jobs j SET lease_until=clock_timestamp()-interval '1 second' "
            "FROM support_app.conversations c WHERE c.id=j.conversation_id AND c.id=%s AND "
            "c.owner_id=%s "
            "AND j.status='running'",
            (target, owner_id),
        )


def wait_live(client: httpx.Client, owner: ProcessOwner) -> None:
    """Wait for the owned API only; recovery scenarios may intentionally omit a worker."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in owner.children):
            raise ValidationError("owned_process_exited")
        try:
            if client.get("/health/live").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    raise ValidationError("liveness_timeout")


def validate_recovery(env: dict[str, str], scenario: str) -> dict[str, int | str]:
    """Exercise one real restart/retry/concurrency window and prove durable result uniqueness."""
    if scenario not in {"after_acceptance", "before_commit", "after_commit", "retry", "concurrent"}:
        raise ValidationError("invalid_scenario")
    dsn = dedicated_database(env.get("VERITYCX_TEST_DATABASE_URL", ""))
    root, cache, pin = source_mode("synthetic")
    manifest = prepare(root, cache, "synthetic", pin)
    approve(root, cache, manifest.aggregate_hash)
    directory = PROJECT_ROOT / ".cache" / "support" / "validation" / str(uuid4())
    auth, first, _ = init_demo(directory)
    owner_id = UUID(load_principals(auth)[0].owner_id)
    child_env = {
        key: value
        for key, value in env.items()
        if key
        not in {
            "OPENAI_API_KEY",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "VERITYCX_MIGRATION_DATABASE_URL",
            "VERITYCX_TEST_MIGRATION_DATABASE_URL",
        }
    }
    child_env.update(
        VERITYCX_DATABASE_URL=dsn,
        VERITYCX_AUTH_FILE=str(auth),
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    processes = ProcessOwner(child_env)
    api_args = ["-c", f"from veritycx.service.validation import serve_test; serve_test({port})"]
    worker_args = [
        "-m",
        "veritycx.orchestration.worker",
        "--provider",
        "deterministic",
        "--corpus-mode",
        "synthetic",
    ]
    try:
        api = processes.launch(api_args)
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=10,
            headers={"Authorization": "Bearer " + first.read_text().strip()},
        ) as client:
            wait_live(client, processes)
            response = client.post(
                "/conversations",
                json={"schema_version": 1},
                headers={"Idempotency-Key": str(uuid4())},
            )
            if response.status_code != 201:
                raise ValidationError("create_failed")
            parent = CreateResponse.model_validate_json(response.content)
            target = UUID(parent.conversation_id)
            key = str(uuid4())
            payload = {"schema_version": 1, "message": fixture_cases()[0].question}

            def submit(request_key: str) -> httpx.Response:
                """Submit an authored question with an explicit request identifier."""
                return client.post(
                    f"/conversations/{target}/turns",
                    json=payload,
                    headers={"Idempotency-Key": request_key},
                )

            if scenario == "concurrent":
                with ThreadPoolExecutor(max_workers=2) as executor:
                    responses = list(executor.map(submit, (key, str(uuid4()))))
                if sorted(r.status_code for r in responses) != [202, 409]:
                    raise ValidationError("concurrent_acceptance_failed")
                accepted = next(r for r in responses if r.status_code == 202)
                key = AcceptanceResponse.model_validate_json(accepted.content).operation_id
            else:
                accepted = submit(key)
            if accepted.status_code != 202:
                raise ValidationError("accept_failed")
            turn = AcceptanceResponse.model_validate_json(accepted.content)
            if turn.turn_id is None:
                raise ValidationError("missing_turn")
            if scenario == "after_acceptance":
                processes.stop(api)
                api = processes.launch(api_args)
                wait_live(client, processes)
            if scenario == "before_commit":
                sentinel = directory / "before-commit"
                code = (
                    "from veritycx.service.validation import serve_paused_worker; "
                    f"serve_paused_worker({str(target)!r}, {str(sentinel)!r})"
                )
                paused = processes.launch(["-c", code])
                deadline = time.monotonic() + 20
                while not sentinel.exists() and time.monotonic() < deadline:
                    if paused.poll() is not None:
                        raise ValidationError("fault_worker_exited")
                    time.sleep(0.05)
                if not sentinel.exists():
                    raise ValidationError("fault_hook_timeout")
                processes.stop(paused)
                expire_owned_lease(dsn, target, owner_id)
            worker = processes.launch(worker_args)
            if scenario == "after_commit":
                deadline = time.monotonic() + 30
                while recovery_counts(dsn, target)[1] == 0 and time.monotonic() < deadline:
                    time.sleep(0.05)
                if recovery_counts(dsn, target)[1] != 1:
                    raise ValidationError("commit_timeout")
                processes.stop(worker)
                processes.stop(api)
                expire_owned_lease(dsn, target, owner_id)
                api = processes.launch(api_args)
                processes.launch(worker_args)
                wait_live(client, processes)
            view = poll_turn(client, str(target), turn.turn_id)
            if (
                len(view.turns) != 1
                or view.turns[0].result is None
                or view.turns[0].result.kind != "answer"
            ):
                raise ValidationError("recovery_result_failed")
            repeated = submit(key)
            if (
                repeated.status_code != 202
                or AcceptanceResponse.model_validate_json(repeated.content).turn_id != turn.turn_id
            ):
                raise ValidationError("retry_changed_turn")
            counts = recovery_counts(dsn, target)
            if counts != (1, 1):
                raise ValidationError("duplicate_or_missing_result")
            return {"scenario": scenario, "turn_count": counts[0], "result_count": counts[1]}
    finally:
        processes.close()


@dataclass
class ValidationSession:
    """Hold owned process handles and redacted client credentials for one isolated run."""

    client: httpx.Client = field(repr=False)
    processes: ProcessOwner = field(repr=False)
    worker: subprocess.Popen[bytes] = field(repr=False)
    second_token: SecretStr = field(repr=False)


@contextmanager
def owned_session(
    env: dict[str, str],
    *,
    live: bool = False,
    corpus_mode: Literal["synthetic", "official"] = "synthetic",
) -> Iterator[ValidationSession]:
    """Launch actual API/worker processes and guarantee handle-only cleanup on every exit."""
    dsn = dedicated_database(env.get("VERITYCX_TEST_DATABASE_URL", ""))
    if live and not env.get("OPENAI_API_KEY"):
        raise ValidationError("missing_provider_credential")
    if corpus_mode == "synthetic":
        root, cache, pin = source_mode("synthetic")
        manifest = prepare(root, cache, "synthetic", pin)
        approve(root, cache, manifest.aggregate_hash)
    else:
        active_corpus("official")
    directory = PROJECT_ROOT / ".cache" / "support" / "validation" / str(uuid4())
    auth, first, second = init_demo(directory)
    child_env = {
        key: value
        for key, value in env.items()
        if key
        not in {
            "OPENAI_API_KEY",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "VERITYCX_MIGRATION_DATABASE_URL",
            "VERITYCX_TEST_MIGRATION_DATABASE_URL",
        }
    }
    if live:
        child_env["OPENAI_API_KEY"] = env["OPENAI_API_KEY"]
    child_env.update(
        VERITYCX_VALIDATION_PROVIDER="openai" if live else "deterministic",
        VERITYCX_VALIDATION_CORPUS=corpus_mode,
        VERITYCX_DATABASE_URL=dsn,
        VERITYCX_AUTH_FILE=str(auth),
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    processes = ProcessOwner(child_env)
    try:
        processes.launch(
            ["-c", f"from veritycx.service.validation import serve_test; serve_test({port})"]
        )
        worker = processes.launch(
            [
                "-m",
                "veritycx.orchestration.worker",
                "--provider",
                "openai" if live else "deterministic",
                "--corpus-mode",
                corpus_mode,
            ]
        )
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=10,
            headers={"Authorization": "Bearer " + first.read_text().strip()},
        ) as client:
            wait_ready(client, processes)
            yield ValidationSession(
                client, processes, worker, SecretStr(second.read_text().strip())
            )
    finally:
        processes.close()


def validate_load(env: dict[str, str]) -> dict[str, int | float | str]:
    """Measure production-cadence queue-inclusive latency and check strict owner isolation."""
    with owned_session(env) as session:

        def conversation(index: int) -> list[float]:
            """Execute three turns for one owner/conversation without sharing customer context."""
            client = session.client
            created = client.post(
                "/conversations",
                json={"schema_version": 1},
                headers={"Idempotency-Key": str(uuid4())},
            )
            if created.status_code != 201:
                raise ValidationError("load_create_failed")
            parent = CreateResponse.model_validate_json(created.content)
            target = parent.conversation_id
            foreign = client.get(
                f"/conversations/{target}",
                headers={"Authorization": "Bearer " + session.second_token.get_secret_value()},
            )
            if foreign.status_code != 404:
                raise ValidationError("cross_owner_leak")
            durations: list[float] = []
            for offset in range(3):
                case = fixture_cases()[(index + offset) % 20]
                key = str(uuid4())
                started = time.monotonic()
                while True:
                    accepted = client.post(
                        f"/conversations/{target}/turns",
                        json={"schema_version": 1, "message": case.question},
                        headers={"Idempotency-Key": key},
                    )
                    if accepted.status_code != 409 or time.monotonic() - started > 10:
                        break
                    time.sleep(0.02)
                if accepted.status_code != 202:
                    raise ValidationError("load_accept_failed")
                turn = AcceptanceResponse.model_validate_json(accepted.content)
                if turn.turn_id is None:
                    raise ValidationError("missing_turn")
                view = poll_turn(client, target, turn.turn_id)
                durations.append(time.monotonic() - started)
                result = next(item.result for item in view.turns if item.turn_id == turn.turn_id)
                if (
                    result is None
                    or result.kind != "answer"
                    or not all(fact in result.text for fact in case.required_facts)
                ):
                    raise ValidationError("load_result_mismatch")
                if len(view.turns) != offset + 1:
                    raise ValidationError("cross_conversation_leak")
            return durations

        with ThreadPoolExecutor(max_workers=10) as executor:
            durations = [
                value for group in executor.map(conversation, range(10)) for value in group
            ]
    p95 = sorted(durations)[math.ceil(0.95 * len(durations)) - 1]
    if p95 > 5:
        raise ValidationError("latency_target_failed")
    result: dict[str, int | float | str] = {
        "turns": len(durations),
        "leaks": 0,
        "p95_seconds": p95,
        "provider": "deterministic",
        "scan_seconds": 1,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "postgresql": "18.6",
    }
    evidence = PROJECT_ROOT / ".cache" / "support" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "load.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return result


def validate_handoff(env: dict[str, str], *, live: bool = False) -> dict[str, int | str]:
    """Exercise all six handoff cases and restart after durable resume acceptance."""
    if live:
        live_preflight(env, live=True)
    mode: Literal["synthetic", "official"] = "official" if live else "synthetic"
    provider = "openai" if live else "deterministic"
    with owned_session(env, live=live, corpus_mode=mode) as session:
        client = session.client
        created = client.post(
            "/conversations", json={"schema_version": 1}, headers={"Idempotency-Key": str(uuid4())}
        )
        if created.status_code != 201:
            raise ValidationError("handoff_create_failed")
        parent = CreateResponse.model_validate_json(created.content)
        url = f"/conversations/{parent.conversation_id}"
        if live:
            _, sections = active_corpus("official")
            if not sections:
                raise ValidationError("empty_corpus")
            question = f"What policy applies to {sections[0].title}?"
            first = submit_and_poll(client, parent.conversation_id, question)
            if not first.turns[-1].result or first.turns[-1].result.kind != "answer":
                raise ValidationError("live_answer_missing")
            session.processes.stop(session.worker)
            session.worker = session.processes.launch(
                [
                    "-m",
                    "veritycx.orchestration.worker",
                    "--provider",
                    provider,
                    "--corpus-mode",
                    mode,
                ]
            )
            live_followup = submit_and_poll(
                client,
                parent.conversation_id,
                f"What else should I know about {sections[0].title}?",
            )
            if (
                len(live_followup.turns) != 2
                or not live_followup.turns[-1].result
                or live_followup.turns[-1].result.kind != "answer"
            ):
                raise ValidationError("live_followup_missing")
        headers = {"Idempotency-Key": str(uuid4())}
        body = {"schema_version": 1, "message": "I want a human agent"}
        accepted = client.post(url + "/turns", headers=headers, json=body)
        turn = AcceptanceResponse.model_validate_json(accepted.content)
        if turn.turn_id is None:
            raise ValidationError("handoff_turn_missing")
        view = poll_turn(client, parent.conversation_id, turn.turn_id)
        # Wait for the graph's final checkpoint/fence release, not just its earlier result commit.
        deadline = time.monotonic() + 15
        while True:
            followup = client.post(
                url + "/turns",
                headers={"Idempotency-Key": str(uuid4())},
                json={"schema_version": 1, "message": "Please retain my latest context"},
            )
            if followup.status_code != 409 or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        if followup.status_code != 202:
            raise ValidationError("handoff_context_failed")
        duplicate = AcceptanceResponse.model_validate_json(
            client.post(url + "/turns", headers=headers, json=body).content
        )
        if duplicate.turn_id != turn.turn_id:
            raise ValidationError("handoff_duplicate")
        view = ConversationView.model_validate_json(client.get(url).content)
        if (
            not view.escalation
            or view.escalation.delivery != "not_connected"
            or "latest context" not in view.escalation.summary
        ):
            raise ValidationError("handoff_context_lost")
        session.processes.stop(session.worker)
        payload = {
            "schema_version": 1,
            "pause_id": view.escalation.pause_id,
            "expected_revision": view.revision,
            "continue_automation": True,
        }
        foreign = client.post(
            url + "/resume",
            headers={
                "Idempotency-Key": str(uuid4()),
                "Authorization": "Bearer " + session.second_token.get_secret_value(),
            },
            json=payload,
        )
        if foreign.status_code != 404:
            raise ValidationError("handoff_owner_leak")
        resume_key = {"Idempotency-Key": str(uuid4())}
        accepted_resume = client.post(url + "/resume", headers=resume_key, json=payload)
        if accepted_resume.status_code != 202:
            raise ValidationError("handoff_resume_failed")
        session.processes.launch(
            [
                "-m",
                "veritycx.orchestration.worker",
                "--provider",
                provider,
                "--corpus-mode",
                mode,
            ]
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            view = ConversationView.model_validate_json(client.get(url).content)
            if view.status == "active":
                break
            time.sleep(0.1)
        if view.status != "active" or len(view.turns) != (4 if live else 2):
            raise ValidationError("handoff_restart_failed")
        retry = client.post(url + "/resume", headers=resume_key, json=payload)
        if retry.status_code != 202 or retry.json()["status"] != "completed":
            raise ValidationError("handoff_resume_duplicate")
        stale = client.post(
            url + "/resume", headers={"Idempotency-Key": str(uuid4())}, json=payload
        )
        if stale.status_code != 409:
            raise ValidationError("handoff_stale_accepted")
    return {
        "suite": "demo" if live else "handoff",
        "model": Settings().model if live else "deterministic-fixture-v1",
        "corpus_version": active_corpus(mode)[0].corpus_version,
        "prompt_version": 1,
        "cases_passed": 6,
        "provider": provider,
        "delivery": "not_connected",
    }


def live_preflight(env: dict[str, str], *, live: bool) -> None:
    """Require explicit paid execution intent and dedicated storage before child startup."""
    if not live:
        raise ValidationError("live_opt_in_required")
    dedicated_database(env.get("VERITYCX_TEST_DATABASE_URL", ""))
    if not env.get("OPENAI_API_KEY"):
        raise ValidationError("missing_provider_credential")


def validate_grounding(env: dict[str, str], *, live: bool) -> dict[str, object]:
    """Collect live 40-case structural evidence; semantic human review stays pending."""
    live_preflight(env, live=live)
    results: list[dict[str, object]] = []
    with owned_session(env, live=True) as session:
        for case in fixture_cases():
            created = session.client.post(
                "/conversations",
                json={"schema_version": 1},
                headers={"Idempotency-Key": str(uuid4())},
            )
            if created.status_code != 201:
                raise ValidationError("grounding_create_failed")
            parent = CreateResponse.model_validate_json(created.content)
            accepted = session.client.post(
                f"/conversations/{parent.conversation_id}/turns",
                json={"schema_version": 1, "message": case.question},
                headers={"Idempotency-Key": str(uuid4())},
            )
            if accepted.status_code != 202:
                raise ValidationError("grounding_accept_failed")
            turn = AcceptanceResponse.model_validate_json(accepted.content)
            if turn.turn_id is None:
                raise ValidationError("missing_turn")
            view = poll_turn(session.client, parent.conversation_id, turn.turn_id)
            result = view.turns[-1].result
            results.append(
                {
                    "case_id": case.id,
                    "kind": result.kind if result else "missing",
                    "citation_count": len(result.citations) if result else 0,
                }
            )
    manifest, _ = active_corpus("synthetic")
    return {
        "suite": "grounding",
        "provider": "openai",
        "model": Settings().model,
        "corpus_version": manifest.corpus_version,
        "prompt_version": 1,
        "human_review": "pending",
        "usage": None,
        "cost": None,
        "cases": results,
    }


def submit_and_poll(client: httpx.Client, target: str, message: str) -> ConversationView:
    """Retry only busy acceptance with one key, then wait for a committed bounded result."""
    key = {"Idempotency-Key": str(uuid4())}
    deadline = time.monotonic() + 15
    while True:
        response = client.post(
            f"/conversations/{target}/turns",
            headers=key,
            json={"schema_version": 1, "message": message},
        )
        if response.status_code != 409 or time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    if response.status_code != 202:
        raise ValidationError("turn_accept_failed")
    turn = AcceptanceResponse.model_validate_json(response.content)
    if turn.turn_id is None:
        raise ValidationError("missing_turn")
    return poll_turn(client, target, turn.turn_id)
