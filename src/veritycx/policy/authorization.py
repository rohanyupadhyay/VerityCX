"""Check server-derived ownership without treating conversation identifiers as credentials."""

from uuid import UUID

from veritycx.persistence.models import ConversationRow
from veritycx.persistence.repository import RepositoryError


def require_owner(owner: UUID, conversation: ConversationRow) -> None:
    """Deny mismatched ownership with the same category used for absent resources."""
    if owner != conversation.owner_id:
        raise RepositoryError("not_found")
