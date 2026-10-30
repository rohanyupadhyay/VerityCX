"""Make the rewrite stage explicit, bounded, and restart-safe before retrieval."""

import asyncio
from hashlib import sha256

from pydantic import ValidationError

from veritycx.persistence.attempts import BudgetError
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import RepositoryError
from veritycx.persistence.rewrites import RewriteLedger
from veritycx.providers.protocol import ProviderError
from veritycx.providers.rewrite import QueryRewriter, RewriteRequest, RewriteResult


async def invoke_rewriter(
    rewriter: QueryRewriter,
    ledger: RewriteLedger,
    job: WorkJob,
    request: RewriteRequest,
    model: str,
) -> RewriteResult:
    """Dispatch at most once; never fall back or replay a call with an unknown outcome."""
    digest = sha256(
        (request.model_dump_json(exclude={"remaining_seconds"}) + "\n" + model).encode()
    ).hexdigest()
    previous = await ledger.lookup(job, digest)
    if previous is not None:
        if previous.status != "succeeded" or previous.result_json is None:
            raise BudgetError("rewrite_attempt_exhausted")
        try:
            return RewriteResult.model_validate_json(previous.result_json)
        except ValidationError:
            raise RepositoryError("incompatible_state") from None
    reservation = await ledger.reserve(job, digest, model, request.prompt_version)
    bounded = request.model_copy(
        update={
            "remaining_seconds": min(request.remaining_seconds, reservation.remaining_seconds, 10.0)
        }
    )
    try:
        async with asyncio.timeout(bounded.remaining_seconds):
            result = await rewriter.rewrite(bounded)
        # Test adapters and future providers get the same strict publication contract.
        result = RewriteResult.model_validate_json(result.model_dump_json())
    except (ProviderError, TimeoutError, ValidationError) as error:
        category = (
            error.category
            if isinstance(error, ProviderError)
            else ("timeout" if isinstance(error, TimeoutError) else "invalid_output")
        )
        await ledger.save(job, None, category)
        raise ProviderError(category) from None
    await ledger.save(job, result)
    return result
