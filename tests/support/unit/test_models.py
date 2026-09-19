"""Reject ambiguous wire payloads before values become trusted application state."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from veritycx.conversations.models import CreateInput, ResumeInput, TurnInput, parse_json
from veritycx.persistence.models import ConversationRow


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version":1,"schema_version":1}',
        b'{"schema_version":true}',
        b'{"schema_version":2}',
        b'{"schema_version":1,"extra":0}',
        b'{"schema_version":NaN}',
        b'{"schema_version":Infinity}',
        b"\xff",
    ],
)
def test_invalid_json(payload: bytes) -> None:
    """Fail closed on duplicates, invalid constants, versions and additional fields."""
    with pytest.raises((ValueError, ValidationError)):
        CreateInput.model_validate(parse_json(payload))


@pytest.mark.parametrize("message", ["", "   ", "x" * 8001])
def test_bad_message(message: str) -> None:
    """Reject missing text or oversized Unicode before turn acceptance."""
    with pytest.raises(ValidationError):
        TurnInput(message=message)


def test_resume_wire_values() -> None:
    """Require canonical UUID and integer revision; never coerce consent."""
    pause = str(uuid4())
    result = ResumeInput(pause_id=pause, expected_revision=1, continue_automation=True)
    assert result.pause_id == pause
    for field, value in [
        ("pause_id", pause.upper()),
        ("expected_revision", True),
        ("continue_automation", 1),
    ]:
        payload: dict[str, object] = result.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError):
            ResumeInput.model_validate(payload)


def test_storage_datetime_and_uuid() -> None:
    """Driver rows must supply typed UUIDs and aware UTC timestamps."""
    row = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "revision": 1,
        "corpus_version": "synthetic-v1",
        "status": "active",
        "customer_count": 0,
        "created_at": datetime.now(UTC),
        "activity_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC),
    }
    assert ConversationRow.model_validate(row).revision == 1
    row["expires_at"] = "2026-01-01"
    with pytest.raises(ValidationError):
        ConversationRow.model_validate(row)
