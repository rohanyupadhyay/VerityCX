"""Validate driver rows into explicit durable entities before business logic."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from veritycx.conversations.models import ClosedModel, TurnResult, VersionedModel


class ConversationRow(VersionedModel):
    """Represent the authoritative owner, lifecycle, count and active work pointer."""

    id: UUID
    owner_id: UUID
    revision: int = Field(ge=1)
    corpus_version: str
    status: Literal["active", "escalation_pending", "deleted"]
    customer_count: int = Field(ge=0, le=100)
    active_job_id: UUID | None = None
    created_at: AwareDatetime
    activity_at: AwareDatetime
    expires_at: AwareDatetime
    deleted_at: AwareDatetime | None = None


class TurnRow(ClosedModel):
    """Represent one accepted message and at most one committed answer."""

    id: UUID
    conversation_id: UUID
    sequence: int = Field(ge=1, le=100)
    request_key: UUID
    text: str = Field(min_length=1, max_length=8000)
    status: Literal["accepted", "running", "completed", "failed"]
    result: TurnResult | None = None
    processing_started_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    created_at: AwareDatetime

    @field_validator("result", mode="before")
    @classmethod
    def validate_json_result(cls, value: object) -> object:
        """Validate JSONB arrays using intentional JSON wire conversion, not Python coercion."""
        if isinstance(value, dict):
            return TurnResult.model_validate_json(json.dumps(value, allow_nan=False))
        return value


class WorkJob(ClosedModel):
    """Bind a worker lease and increasing fence to one durable execution."""

    id: UUID
    conversation_id: UUID
    turn_id: UUID | None = None
    kind: Literal["turn", "resume", "pause_repair"]
    status: Literal["accepted", "running", "completed", "failed"]
    worker_id: UUID | None = None
    fence: int = Field(ge=0)
    lease_until: AwareDatetime | None = None
    checkpoint_id: str | None = None
    checkpoint_ns: str = ""
    failure_code: Literal["control_failed", "incompatible_state"] | None = None
    recovery: Literal["retry_with_new_pause", "operator_required"] | None = None
    created_at: AwareDatetime


class WorkerHeartbeat(ClosedModel):
    """Track worker liveness without conversation content."""

    worker_id: UUID
    last_seen: datetime


class OperationRow(ClosedModel):
    """Bind an owner-scoped idempotency key to one canonical request digest."""

    owner_id: UUID
    request_key: UUID
    kind: Literal["create", "turn", "resume", "delete"]
    conversation_id: UUID
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    resource_id: UUID | None = None
    created_at: AwareDatetime


class ProviderAttemptRow(ClosedModel):
    """Retain reservations and validated journal output across worker restarts."""

    turn_id: UUID
    ordinal: int = Field(ge=1, le=2)
    status: Literal["reserved", "succeeded", "failed"]
    request_digest: str
    result_json: str | None = None
    failure_category: str | None = None
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None


class EscalationRow(ClosedModel):
    """Track current or consumed pauses without claiming external delivery."""

    id: UUID
    conversation_id: UUID
    triggering_turn_id: UUID
    reason: str
    summary: str = Field(max_length=4000)
    source_ids: list[str]
    pause_id: UUID
    status: Literal["pending", "cancelled"]
    consumed_operation_id: UUID | None = None
    created_at: AwareDatetime
    consumed_at: AwareDatetime | None = None


class AuditEventRow(ClosedModel):
    """Keep local associations separate from explicitly constructed export metadata."""

    id: UUID
    conversation_id: UUID
    turn_id: UUID
    correlation_id: UUID
    stage: str
    outcome: str
    route: str
    source_ids: list[str]
    elapsed_ms: int = Field(ge=0)
    failure_category: str | None = None
    model: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
