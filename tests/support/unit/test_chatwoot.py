"""Verify signed Chatwoot intake, private configuration and safe remote operations."""

import hashlib
import hmac
import json
from contextlib import nullcontext
from uuid import uuid4

import httpx
import pytest

from veritycx.handoff.client import ChatwootClient, ChatwootRemoteError
from veritycx.handoff.configuration import ChatwootConfigurationError, load_chatwoot_configuration
from veritycx.handoff.events import normalize_event, verify_signature
from veritycx.service.runtime import run_async


def environment() -> dict[str, str]:
    """Return synthetic complete configuration with distinguishable secrets."""
    return {
        "VERITYCX_CHATWOOT_URL": "http://127.0.0.1:3000",
        "VERITYCX_CHATWOOT_ACCOUNT_ID": "1",
        "VERITYCX_CHATWOOT_INBOX_ID": "2",
        "VERITYCX_CHATWOOT_WEBSITE_TOKEN": "public-widget",
        "VERITYCX_CHATWOOT_API_TOKEN": "private-api-token",
        "VERITYCX_CHATWOOT_BOT_TOKEN": "private-bot-token",
        "VERITYCX_CHATWOOT_WEBHOOK_SECRET": "private-signing-secret",
    }


def payload() -> dict[str, object]:
    """Return a realistic incoming signed AgentBot envelope."""
    return {
        "event": "message_created",
        "id": 9,
        "account": {"id": 1},
        "inbox": {"id": 2},
        "conversation": {"id": 7, "inbox_id": 2},
        "message_type": "incoming",
        "private": False,
        "content": "Policy question",
    }


def test_configuration_private_and_disabled() -> None:
    """Expose only website fields; reject partial configuration without leaking values."""
    assert load_chatwoot_configuration({}) is None
    assert load_chatwoot_configuration(dict.fromkeys(environment(), "")) is None
    config = load_chatwoot_configuration(environment())
    assert config is not None
    assert config.public() == {
        "enabled": True,
        "base_url": "http://127.0.0.1:3000",
        "website_token": "public-widget",
    }
    assert "private-" not in repr(config)
    with pytest.raises(ChatwootConfigurationError, match="invalid_chatwoot_configuration"):
        load_chatwoot_configuration({"VERITYCX_CHATWOOT_API_TOKEN": "do-not-disclose"})


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://u:p@example.com",
        "https://example.com/path",
        "https://example.com?secret=x",
        "https://example.com/#x",
        "http://127.0.0.1.evil:3000",
        "https://example.com\\evil",
        "https://example.com:bad",
    ],
)
def test_configuration_rejects_unsafe_origin(url: str) -> None:
    """Prevent credential, path and insecure network origins in the public contract."""
    env = environment()
    env["VERITYCX_CHATWOOT_URL"] = url
    with pytest.raises(ChatwootConfigurationError):
        load_chatwoot_configuration(env)


def test_signature_binds_timestamp_and_exact_body() -> None:
    """Reject body tampering, stale signatures and malformed signatures."""
    body = json.dumps(payload()).encode()
    secret = "test-secret"  # noqa: S105 - synthetic signing fixture.
    stamp = "1800000000"
    signature = hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    verify_signature(body, stamp, "sha256=" + signature, secret, now=1800000000)
    for candidate, timestamp, signed in [
        (body + b" ", stamp, signature),
        (body, "1799999000", signature),
        (body, stamp, "bad"),
        (body, "1800001000", signature),
    ]:
        with pytest.raises(ValueError, match="invalid_webhook_signature"):
            verify_signature(candidate, timestamp, signed, secret, now=1800000000)


def test_event_normalization_allowlist_and_dedup() -> None:
    """Keep only bounded incoming customer content and stable message identity."""
    config = load_chatwoot_configuration(environment())
    assert config is not None
    event = normalize_event(payload(), config)
    assert event is not None and event.key == "message:9" and event.conversation_id == 7
    mutations: list[dict[str, object]] = [
        {"private": True},
        {"message_type": "outgoing"},
        {"account": {"id": 99}},
        {"inbox": {"id": 99}},
        {"content": "x" * 8001},
        {"id": True},
    ]
    for mutation in mutations:
        changed = payload() | mutation
        with (
            pytest.raises(ValueError)
            if mutation.keys() & {"account", "inbox", "content", "id"}
            else nullcontext()
        ):
            result = normalize_event(changed, config)
            assert result is None


def test_client_ownership_and_stable_metadata() -> None:
    """Use exact account endpoints and correlation metadata without HTTP retries."""

    async def exercise() -> None:
        """Exercise actual httpx serialization with a synthetic transport."""
        config = load_chatwoot_configuration(environment())
        assert config is not None
        calls: list[httpx.Request] = []
        turn_id = uuid4()

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "id": 7,
                        "inbox_id": 2,
                        "status": "pending",
                        "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                    },
                )
            return httpx.Response(200, json={"id": 12})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = ChatwootClient(config, http)
            assert (await client.conversation(7)).bot_owned
            await client.message(7, turn_id, "Answer", private=False)
        assert len(calls) == 2
        assert calls[-1].url.path == "/api/v1/accounts/1/conversations/7/messages"
        assert json.loads(calls[-1].content)["content_attributes"]["veritycx_turn_id"] == str(
            turn_id
        )

    run_async(exercise())


def test_client_reconciles_and_sanitizes_failures() -> None:
    """Find an earlier publication by marker and suppress provider diagnostics."""

    async def exercise() -> None:
        config = load_chatwoot_configuration(environment())
        assert config is not None
        marker = uuid4()

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/messages"):
                return httpx.Response(
                    200,
                    json={
                        "payload": [
                            {"id": 14, "content_attributes": {"veritycx_turn_id": str(marker)}}
                        ]
                    },
                )
            return httpx.Response(500, text="private-provider-details")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = ChatwootClient(config, http)
            assert await client.find_message(7, marker) == 14
            with pytest.raises(ChatwootRemoteError, match="chatwoot_unavailable") as caught:
                await client.conversation(7)
            assert "private-provider" not in str(caught.value)

    run_async(exercise())


@pytest.mark.parametrize(
    "status,meta,expected",
    [
        ("pending", {"assignee": {"id": 3}, "assignee_type": "AgentBot"}, True),
        ("pending", {}, False),
        ("pending", {"assignee": None, "assignee_type": "AgentBot"}, False),
        ("pending", {"assignee": {"id": 3}, "assignee_type": "User"}, False),
        ("pending", {"assignee": None, "assignee_type": "User"}, False),
        ("open", {}, False),
        ("resolved", {}, False),
        ("snoozed", {}, False),
    ],
)
def test_client_live_ownership(status: str, meta: dict[str, object], expected: bool) -> None:
    """Recognize the actual pinned assignee contract and suppress every human-owned state."""

    async def exercise() -> None:
        config = load_chatwoot_configuration(environment())
        assert config is not None

        def remote(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"id": 7, "inbox_id": 2, "status": status, "meta": meta}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
            assert (await ChatwootClient(config, http).conversation(7)).bot_owned is expected

    run_async(exercise())


def test_status_events_normalize_without_trusting_ownership() -> None:
    """Accept the pinned conversation event shape as a wakeup, without customer ownership fields."""
    config = load_chatwoot_configuration(environment())
    assert config is not None
    event = normalize_event(
        {
            "event": "conversation_status_changed",
            "id": 7,
            "inbox_id": 2,
            "account": {"id": 1},
            "status": "pending",
            "meta": {"assignee_type": "AgentBot"},
        },
        config,
    )
    assert event is not None and event.content is None and event.message_id is None
    assert event.key.startswith("status:")


def test_routes_disabled_and_unsigned_webhook() -> None:
    """Return an honest public disabled contract and require authentication before pool access."""
    from fastapi import FastAPI

    from veritycx.handoff.routes import register_chatwoot
    from veritycx.persistence.database import DatabasePool

    async def exercise() -> None:
        def no_pool() -> DatabasePool:
            raise AssertionError("pool must not be touched")

        app = FastAPI()
        register_chatwoot(app, None, no_pool)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            response = await http.get("/chat/config")
            assert response.json() == {"enabled": False, "base_url": None, "website_token": None}
            assert (await http.post("/integrations/chatwoot/webhook")).status_code == 503
        app = FastAPI()
        register_chatwoot(app, load_chatwoot_configuration(environment()), no_pool)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            assert (
                await http.post("/integrations/chatwoot/webhook", json=payload())
            ).status_code == 401
            assert (
                await http.post("/integrations/chatwoot/webhook", content=b"x" * 65537)
            ).status_code == 413
            public = (await http.get("/chat/config")).text
            assert "private-" not in public and "API_TOKEN" not in public

    run_async(exercise())


def test_routes_acknowledge_only_after_normalized_persistence() -> None:
    """Verify the real signature boundary commits its bounded event before sending HTTP202."""
    import time
    from unittest.mock import AsyncMock, Mock, patch

    from fastapi import FastAPI

    from veritycx.handoff.routes import register_chatwoot
    from veritycx.persistence.database import DatabasePool

    async def exercise() -> None:
        config = load_chatwoot_configuration(environment())
        assert config is not None
        app = FastAPI()
        pool = Mock(spec=DatabasePool)
        register_chatwoot(app, config, lambda: pool)
        body = json.dumps(payload()).encode()
        stamp = str(int(time.time()))
        signed = hmac.new(
            config.webhook_secret.get_secret_value().encode(),
            stamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        saved = AsyncMock()
        with patch("veritycx.handoff.routes.ChatwootStore") as store:
            store.return_value.persist = saved
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as http:
                response = await http.post(
                    "/integrations/chatwoot/webhook",
                    content=body,
                    headers={
                        "X-Chatwoot-Timestamp": stamp,
                        "X-Chatwoot-Signature": "sha256=" + signed,
                    },
                )
            assert response.status_code == 202
            saved.assert_awaited_once()
            event = saved.call_args.args[0]
            assert event.content == "Policy question" and event.key == "message:9"

    run_async(exercise())


@pytest.mark.parametrize("private", [False, True])
def test_client_routes_read_and_write_tokens(private: bool) -> None:
    """Read history with an account user token and post public/private messages as the AgentBot."""

    async def exercise() -> None:
        env = environment() | {"VERITYCX_CHATWOOT_BOT_TOKEN": "private-bot-token"}
        config = load_chatwoot_configuration(env)
        assert config is not None
        marker = uuid4()
        calls: list[tuple[str, str, str]] = []

        def remote(request: httpx.Request) -> httpx.Response:
            token = request.headers["api_access_token"]
            calls.append((request.method, request.url.path, token))
            assert request.url.host == "127.0.0.1"
            assert request.url.path.startswith("/api/v1/accounts/1/conversations/7")
            if request.method == "POST" and request.url.path.endswith("/messages"):
                if token != "private-bot-token":  # noqa: S105 - synthetic transport credential.
                    return httpx.Response(401, json={"error": "must post as AgentBot"})
                return httpx.Response(200, json={"id": 12})
            if token != "private-api-token":  # noqa: S105 - synthetic transport credential.
                return httpx.Response(401, json={"error": "account user token required"})
            if request.url.path.endswith("/messages"):
                return httpx.Response(
                    200,
                    json={
                        "payload": [
                            {"id": 12, "content_attributes": {"veritycx_turn_id": str(marker)}}
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": 7,
                    "inbox_id": 2,
                    "status": "pending",
                    "meta": {"assignee_type": "AgentBot", "assignee": {"id": 3}},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
            client = ChatwootClient(config, http)
            assert (await client.conversation(7)).bot_owned
            assert await client.find_message(7, marker) == 12
            await client.open(7)
            assert await client.message(7, marker, "Answer", private=private) == 12
        assert [token for _, _, token in calls] == ["private-api-token"] * 3 + ["private-bot-token"]
        assert "private-bot-token" not in repr(config)
        assert "private-bot-token" not in str(config.public())

    run_async(exercise())


def test_configuration_requires_separate_bot_token() -> None:
    """A six-field setup must fail instead of silently giving the wrong sender/read permissions."""
    env = environment()
    env.pop("VERITYCX_CHATWOOT_BOT_TOKEN", None)
    with pytest.raises(ChatwootConfigurationError, match="invalid_chatwoot_configuration"):
        load_chatwoot_configuration(env)
