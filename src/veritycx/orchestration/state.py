"""Define primitive checkpoint state; application records retain all authority."""

from typing import TypedDict


class ConversationState(TypedDict):
    """Describe a validated working projection, never trusted ownership or budgets."""

    schema_version: int
    conversation_id: str
    job_id: str
    turn_id: str | None
    corpus_version: str
    route: str
    evidence_ids: list[str]
    provider_result_id: str | None
    pause_id: str | None
    input_context: list[dict[str, str]]
