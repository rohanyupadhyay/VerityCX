"""Intercept explicit trace payloads and prove failure isolation without a trace account."""

import json
from uuid import uuid4

import httpx
import pytest
from langsmith import Client, traceable, tracing_context
from pydantic import SecretStr

from veritycx.observability.export import TraceExporter, metadata
from veritycx.persistence.models import AuditEventRow
from veritycx.service.runtime import run_async


def test_export_allowlist() -> None:
    """Private associations never enter the fresh export object; unknown usage stays null."""
    event = AuditEventRow(
        id=uuid4(),
        conversation_id=uuid4(),
        turn_id=uuid4(),
        correlation_id=uuid4(),
        stage="result",
        outcome="answer",
        route="knowledge",
        source_ids=["synthetic:0001"],
        elapsed_ms=5,
    )
    payload = metadata(event, "deterministic")
    encoded = json.dumps(payload)
    assert str(event.conversation_id) not in encoded and str(event.turn_id) not in encoded
    assert payload["input_tokens"] is None
    assert "summary" not in payload and "inputs" not in payload


def test_export_failure_isolation() -> None:
    """A transport failure never reflects a secret or raises into customer execution."""

    def fail(request: httpx.Request) -> httpx.Response:
        """Intercept a precise empty-input export and fail with a private canary."""
        value = json.loads(request.content)
        assert value["inputs"] == {} and value["outputs"] == {}
        raise httpx.ConnectError("PRIVATE_EXCEPTION_CANARY")

    async def exercise() -> None:
        """Use a mock transport so this test cannot contact an external account."""
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            exporter = TraceExporter(client, SecretStr("PRIVATE_KEY_CANARY"), "test")
            assert not await exporter.send({"correlation_id": str(uuid4())})
            assert exporter.failures == 1

    run_async(exercise())


def test_nested_ambient_tracing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nested and error spans cannot escape a disabled worker tracing context."""
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    captured: list[object] = []

    def capture(self: object, *args: object, **kwargs: object) -> None:
        """Intercept SDK trace creation without starting a network request."""
        captured.append(kwargs)

    monkeypatch.setattr(Client, "create_run", capture)

    @traceable
    def child(value: str) -> str:
        """Create a nested exception whose sensitive text must stay local."""
        raise ValueError(value)

    @traceable
    def parent(value: str) -> str:
        """Try automatic child tracing with customer content in inherited ambient mode."""
        return child(value)

    with tracing_context(enabled=False), pytest.raises(ValueError, match="BODY_CANARY"):
        parent("BODY_CANARY")
    assert captured == []
