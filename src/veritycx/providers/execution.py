"""Apply the persisted attempt/deadline budget around any provider implementation."""

import asyncio
from hashlib import sha256

from veritycx.persistence.attempts import AttemptLedger
from veritycx.persistence.models import WorkJob
from veritycx.policy.outputs import validate_result
from veritycx.providers.protocol import (
    KnowledgeProvider,
    ProviderError,
    ProviderRequest,
    ProviderResult,
)


async def invoke_provider(
    provider: KnowledgeProvider, ledger: AttemptLedger, job: WorkJob, request: ProviderRequest
) -> ProviderResult:
    """Reuse journaled output or reserve at most two calls, persisting before continuation."""
    digest = sha256(request.model_dump_json(exclude={"remaining_seconds"}).encode()).hexdigest()
    previous = await ledger.succeeded(job, digest)
    if previous is not None:
        validate_result(request, previous)
        return previous
    while True:
        reservation = await ledger.reserve(job, digest)
        bounded = request.model_copy(
            update={"remaining_seconds": min(60.0, reservation.remaining_seconds)}
        )
        try:
            async with asyncio.timeout(min(30.0, reservation.remaining_seconds)):
                result = await provider.generate(bounded)
            validate_result(bounded, result)
        except (ProviderError, TimeoutError) as error:
            category = error.category if isinstance(error, ProviderError) else "timeout"
            await ledger.save(job, reservation, None, category)
            if reservation.ordinal >= 2:
                raise ProviderError(category) from None
            await asyncio.sleep(min(1.0, max(0.0, reservation.remaining_seconds)))
            continue
        await ledger.save(job, reservation, result)
        return result
