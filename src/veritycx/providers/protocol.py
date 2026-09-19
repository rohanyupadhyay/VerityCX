"""Define provider requests and results without tools, owners or database capabilities."""

from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from veritycx.conversations.models import ClosedModel, VersionedModel
from veritycx.knowledge.models import EvidenceSection


class ContextMessage(ClosedModel):
    """Preserve role boundaries in bounded prior conversation context."""

    role: Literal["user", "assistant"]
    text: str = Field(max_length=8000)


class ProviderRequest(VersionedModel):
    """Supply only the current question, selected evidence and remaining budget."""

    correlation_id: str
    question: str = Field(min_length=1, max_length=8000)
    context: tuple[ContextMessage, ...] = ()
    evidence: tuple[EvidenceSection, ...] = Field(max_length=6)
    remaining_seconds: float = Field(gt=0, le=60)
    prompt_version: Literal[1] = 1

    @model_validator(mode="after")
    def bounded_context(self) -> Self:
        """Enforce aggregate limits, independent of the number of messages."""
        if sum(len(item.text) for item in self.context) > 16000:
            raise ValueError("context_limit")
        if sum(len(item.content) for item in self.evidence) > 12000:
            raise ValueError("evidence_limit")
        return self


class Claim(ClosedModel):
    """Associate an untrusted policy claim with selected section identifiers."""

    text: str = Field(min_length=1, max_length=8000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=6)


class Usage(ClosedModel):
    """Represent observed token counts without inventing missing measurements."""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ProviderResult(VersionedModel):
    """Validate bounded output shape; a separate policy check validates citations."""

    disposition: Literal["answer", "clarify", "abstain"]
    claims: tuple[Claim, ...] = ()
    text: str | None = Field(default=None, min_length=1, max_length=8000)
    model: str
    usage: Usage | None = None

    @model_validator(mode="after")
    def valid_disposition(self) -> Self:
        """Forbid unsupported claim-bearing abstentions and oversized answers."""
        if self.disposition == "answer":
            if not self.claims or self.text is not None:
                raise ValueError("invalid_answer")
        elif self.claims or self.text is None:
            raise ValueError("invalid_nonanswer")
        if sum(len(claim.text) for claim in self.claims) + len(self.text or "") > 8000:
            raise ValueError("output_limit")
        return self


class ProviderError(Exception):
    """Expose only a fixed failure category suitable for durable recording."""

    def __init__(
        self, category: Literal["timeout", "provider_unavailable", "invalid_output"]
    ) -> None:
        """Store a safe category without retaining a raw upstream exception."""
        self.category = category
        super().__init__(category)


class KnowledgeProvider(Protocol):
    """Provide one bounded generation call with no internal automatic retries."""

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Return validated output or raise a categorized ProviderError."""
        ...
