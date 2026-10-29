"""Expose public widget configuration and authenticated durable AgentBot intake."""

from collections.abc import Callable
from typing import Literal

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from veritycx.conversations.models import parse_json
from veritycx.handoff.configuration import ChatwootConfiguration
from veritycx.handoff.events import MAX_WEBHOOK_BYTES, normalize_event, verify_signature
from veritycx.handoff.store import ChatwootStore
from veritycx.knowledge.configuration import active_corpus
from veritycx.persistence.database import DatabasePool


def register_chatwoot(
    app: FastAPI,
    configuration: ChatwootConfiguration | None,
    pool_getter: Callable[[], DatabasePool],
    *,
    corpus_mode: Literal["synthetic", "official"] = "synthetic",
) -> None:
    """Register optional routes without requiring browser authorization or exposing secrets."""

    @app.get("/chat/config")
    async def config() -> JSONResponse:
        """Return the closed public widget contract even when the integration is disabled."""
        value = (
            configuration.public()
            if configuration
            else {"enabled": False, "base_url": None, "website_token": None}
        )
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    @app.post("/integrations/chatwoot/webhook")
    async def webhook(request: Request) -> JSONResponse:
        """Acknowledge relevant events only after a bounded authenticated projection commits."""
        if configuration is None:
            return JSONResponse({"error": "chatwoot_disabled"}, status_code=503)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_WEBHOOK_BYTES:
                return JSONResponse({"error": "payload_too_large"}, status_code=413)
            body.extend(chunk)
        try:
            verify_signature(
                bytes(body),
                request.headers.get("X-Chatwoot-Timestamp", ""),
                request.headers.get("X-Chatwoot-Signature", ""),
                configuration.webhook_secret.get_secret_value(),
            )
        except ValueError:
            return JSONResponse({"error": "invalid_webhook_signature"}, status_code=401)
        try:
            event = normalize_event(parse_json(bytes(body)), configuration)
        except (ValueError, TypeError, RecursionError):
            return JSONResponse({"error": "invalid_chatwoot_event"}, status_code=422)
        if event is not None:
            manifest, _ = active_corpus(corpus_mode)
            await ChatwootStore(pool_getter(), configuration).persist(
                event, manifest.corpus_version
            )
        return JSONResponse({"accepted": True}, status_code=202)
