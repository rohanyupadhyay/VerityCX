"""Define closed wire contracts and reject ambiguous JSON before model validation."""

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClosedModel(BaseModel):
    """Forbid unknown fields, coercion and mutation at application boundaries."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, allow_inf_nan=False, hide_input_in_errors=True
    )


class VersionedModel(ClosedModel):
    """Accept only the supported integer wire version."""

    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        """Disallow boolean equality with the integer version literal."""
        if type(value) is not int:
            raise ValueError("invalid_version")
        return value


def canonical_uuid(value: str) -> str:
    """Require lowercase canonical UUID text rather than accepting aliases."""
    if str(UUID(value)) != value:
        raise ValueError("invalid_identifier")
    return value


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate keys at every JSON object nesting level."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def reject_constant(value: str) -> object:
    """Reject JSON extensions for nonfinite numeric values."""
    raise ValueError("invalid_number")


def parse_json(payload: bytes) -> object:
    """Decode strict UTF-8 JSON, returning an untrusted value for model validation."""
    result: object = json.loads(
        payload.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant
    )
    return result


class CreateInput(VersionedModel):
    """Accept a create intent with no customer-selected identity or source."""


class TurnInput(VersionedModel):
    """Bound customer text while preserving its exact accepted characters."""

    message: str = Field(min_length=1, max_length=8000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Reject whitespace-only input without trimming valid messages."""
        if not value.strip():
            raise ValueError("empty_message")
        return value


class ResumeInput(VersionedModel):
    """Accept only explicit consent for the current pause and revision."""

    pause_id: str
    expected_revision: int = Field(ge=1)
    continue_automation: Literal[True]

    @field_validator("pause_id")
    @classmethod
    def validate_pause(cls, value: str) -> str:
        """Require a canonical pause identifier."""
        return canonical_uuid(value)

    @field_validator("continue_automation", mode="before")
    @classmethod
    def explicit_consent(cls, value: object) -> object:
        """Numeric one and strings are not explicit boolean consent."""
        if value is not True:
            raise ValueError("explicit_consent_required")
        return value


class Citation(ClosedModel):
    """Expose approved source attribution without local filesystem paths."""

    corpus_version: str
    document_id: str
    section_id: str
    title: str


class TurnResult(ClosedModel):
    """Persist one bounded customer result, including truthful pending escalation."""

    kind: Literal["answer", "clarify", "abstain", "unavailable", "escalation", "error"]
    text: str = Field(min_length=1, max_length=8000)
    citations: tuple[Citation, ...] = ()
    failure_category: str | None = None


PositiveRevision = Annotated[int, Field(ge=1)]


class CreateResponse(VersionedModel):
    """Validate the durable creation projection used by clients and acceptance drivers."""

    conversation_id: str
    revision: int
    status: str
    expires_at: str


class ResumeFailure(ClosedModel):
    """Expose only reviewed control failure and recovery categories."""

    code: Literal["control_failed", "incompatible_state"]
    recovery: Literal["retry_with_new_pause", "operator_required"]


class ResumeOperationView(ClosedModel):
    """Describe a durable resume without exposing graph state."""

    operation_id: str
    status: Literal["accepted", "running", "completed", "failed"]
    failure: ResumeFailure | None = None


class EscalationView(ClosedModel):
    """Expose a usable pause with an explicit disconnected delivery status."""

    pause_id: str
    reason: str
    summary: str = Field(max_length=4000)
    status: Literal["pending"] = "pending"
    delivery: Literal["not_connected"] = "not_connected"


class AcceptanceResponse(VersionedModel):
    """Validate an accepted operation without inferring completion from HTTP status."""

    operation_id: str
    conversation_id: str
    turn_id: str | None
    status: str
    poll_url: str
    failure: ResumeFailure | None = None


class TurnView(ClosedModel):
    """Expose ordered accepted messages and their bounded public result."""

    turn_id: str
    sequence: int
    message: str
    status: str
    result: TurnResult | None


class ConversationView(CreateResponse):
    """Validate the current knowledge-only polling projection."""

    turns: list[TurnView]
    escalation: EscalationView | None = None
    latest_resume_operation: ResumeOperationView | None = None
