"""Authenticate raw AgentBot webhooks and retain a closed bounded event projection."""

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass

from veritycx.handoff.configuration import ChatwootConfiguration

MAX_WEBHOOK_BYTES = 65536


def verify_signature(
    body: bytes, timestamp: str, signature: str, secret: str, *, now: float | None = None
) -> None:
    """Verify Chatwoot 4.19.1 timestamp.raw_body HMAC with five-minute replay tolerance."""
    now = time.time() if now is None else now
    signed = signature.removeprefix("sha256=")
    if (
        not re.fullmatch(r"[0-9]{1,12}", timestamp)
        or abs(now - int(timestamp)) > 300
        or not re.fullmatch(r"[0-9a-f]{64}", signed)
    ):
        raise ValueError("invalid_webhook_signature")
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signed):
        raise ValueError("invalid_webhook_signature")


def object_value(value: object) -> dict[str, object]:
    """Require an ordinary object while keeping untrusted JSON values typed."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("invalid_chatwoot_event")
    return value


def positive_id(value: object) -> int:
    """Reject booleans and oversized identifiers before SQL or URL construction."""
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise ValueError("invalid_chatwoot_event")
    return value


@dataclass(frozen=True)
class ChatwootEvent:
    """Retain only the external thread identity, stable event key and bounded customer text."""

    key: str
    conversation_id: int
    message_id: int | None
    content: str | None


def normalize_event(value: object, config: ChatwootConfiguration) -> ChatwootEvent | None:
    """Allow one configured account/inbox; discard private, outgoing and irrelevant events."""
    data = object_value(value)
    kind = data.get("event")
    if kind not in (
        "message_created",
        "conversation_status_changed",
        "conversation_updated",
        "conversation_opened",
        "conversation_resolved",
    ):
        return None
    if kind == "message_created" and (
        data.get("private") is not False
        or isinstance(data.get("message_type"), bool)
        or data.get("message_type") not in ("incoming", 0)
    ):
        return None
    account = positive_id(object_value(data.get("account")).get("id"))
    if account != config.account_id:
        raise ValueError("invalid_chatwoot_event")
    if kind == "message_created":
        conversation = object_value(data.get("conversation"))
        inbox = positive_id(object_value(data.get("inbox")).get("id"))
        if positive_id(conversation.get("inbox_id")) != inbox:
            raise ValueError("invalid_chatwoot_event")
        external_id = positive_id(conversation.get("id"))
    else:
        inbox = positive_id(data.get("inbox_id"))
        external_id = positive_id(data.get("id"))
    if inbox != config.inbox_id:
        raise ValueError("invalid_chatwoot_event")
    if kind != "message_created":
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return ChatwootEvent("status:" + digest, external_id, None, None)
    message_id = positive_id(data.get("id"))
    content = data.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > 8000:
        raise ValueError("invalid_chatwoot_event")
    return ChatwootEvent(f"message:{message_id}", external_id, message_id, content)
