"""Verify restricted primitive/interrupt serialization and trusted restore binding."""

from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.types import Interrupt

from veritycx.persistence.checkpoints import restricted_serializer, validate_checkpoint


def test_restricted_roundtrip() -> None:
    """Preserve primitives and the framework Interrupt without application imports."""
    serializer = restricted_serializer()
    value = {"message": "synthetic", "interrupt": Interrupt(value="pending", id="test")}
    assert serializer.loads_typed(serializer.dumps_typed(value)) == value
    with pytest.raises(NotImplementedError):
        serializer.loads_typed(("pickle", b"malicious"))


def test_restore_binding() -> None:
    """Reject foreign conversations, schema drift and unapproved corpus versions."""
    conversation, job = uuid4(), uuid4()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {
        "schema_version": 1,
        "conversation_id": str(conversation),
        "job_id": str(job),
        "corpus_version": "fixture",
    }
    validate_checkpoint(checkpoint, conversation, job, "fixture")
    for key, value in [
        ("schema_version", 2),
        ("conversation_id", str(uuid4())),
        ("job_id", str(uuid4())),
        ("corpus_version", "foreign"),
    ]:
        invalid = checkpoint.copy()
        invalid["channel_values"] = dict(checkpoint["channel_values"], **{key: value})
        with pytest.raises(ValueError, match="incompatible_state"):
            validate_checkpoint(invalid, conversation, job, "fixture")
