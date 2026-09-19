"""Parse only closed document envelopes from bounded verified source bytes."""

from pathlib import Path

from pydantic import ValidationError

from veritycx.conversations.models import parse_json
from veritycx.knowledge.models import KnowledgeDocument
from veritycx.policy.sources import SourceError, verified_bytes


def parse_document(raw: bytes) -> KnowledgeDocument:
    """Reject duplicate JSON keys, wrong schemas and invalid UTF-8 without leaking content."""
    try:
        return KnowledgeDocument.model_validate(parse_json(raw))
    except (ValueError, ValidationError):
        raise SourceError("invalid_document") from None


def read_document(root: Path, relative: str) -> KnowledgeDocument:
    """Load a single allowed document without invoking the acquisition inspector."""
    return parse_document(verified_bytes(root, relative))
