"""Define immutable trusted command identities separate from customer payloads."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class WorkerAuthority:
    """Bind one claimed job to its trusted worker token and monotonic fence."""

    conversation_id: UUID
    job_id: UUID
    worker_id: UUID
    fence: int


@dataclass(frozen=True)
class OwnerCommand:
    """Bind an authenticated owner to an idempotency key and target conversation."""

    owner_id: UUID
    request_key: UUID
    conversation_id: UUID
