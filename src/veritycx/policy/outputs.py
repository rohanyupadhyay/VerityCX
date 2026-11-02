"""Constrain output publication to selected evidence; render citations on the server."""

from veritycx.conversations.models import Citation, TurnResult
from veritycx.knowledge.scope import OVERVIEW_SCOPE_NOTE
from veritycx.providers.protocol import ProviderError, ProviderRequest, ProviderResult


def validate_result(request: ProviderRequest, result: ProviderResult) -> TurnResult:
    """Reject invented/out-of-selection citations and render one bounded customer result."""
    if result.disposition != "answer":
        return TurnResult(kind=result.disposition, text=result.text or "Unable to answer.")
    selected = {section.section_id: section for section in request.evidence}
    citations: dict[str, Citation] = {}
    for claim in result.claims:
        for identifier in claim.evidence_ids:
            section = selected.get(identifier)
            if section is None:
                raise ProviderError("invalid_output")
            citations[identifier] = Citation(
                corpus_version=section.corpus_version,
                document_id=section.document_id,
                section_id=identifier,
                title=section.title,
            )
    text = "\n".join(claim.text for claim in result.claims)
    if len(text) > request.answer_text_limit:
        raise ProviderError("invalid_output")
    if (
        request.search_context is not None
        and request.search_context.search_scope.scope == "category_overview"
    ):
        text += "\n" + OVERVIEW_SCOPE_NOTE
    return TurnResult(kind="answer", text=text, citations=tuple(citations.values()))
