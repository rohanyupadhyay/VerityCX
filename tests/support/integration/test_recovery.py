"""Run the twenty specified restart/retry/concurrency cases through owned subprocesses."""

import os
from typing import Literal

import pytest

from veritycx.service.validation import validate_recovery

pytestmark = pytest.mark.support_db


@pytest.mark.parametrize("repeat", range(4))
@pytest.mark.parametrize(
    "scenario", ["after_acceptance", "before_commit", "after_commit", "retry", "concurrent"]
)
def test_recovery_subprocesses(
    test_database_url: str,
    scenario: Literal["after_acceptance", "before_commit", "after_commit", "retry", "concurrent"],
    repeat: int,
) -> None:
    """Repeat every failure window four times and inspect durable uniqueness."""
    result = validate_recovery(
        dict(os.environ, VERITYCX_TEST_DATABASE_URL=test_database_url), scenario
    )
    assert result["turn_count"] == 1
    assert result["result_count"] == 1
    assert repeat >= 0


def test_corrupt_pointer_blocks_new_work(test_database_url: str) -> None:
    """Corrupt durable pointers preserve evidence and require operator remediation."""
    from uuid import uuid4

    from veritycx.knowledge.configuration import active_corpus
    from veritycx.orchestration.worker import process_job
    from veritycx.persistence.database import database_pool
    from veritycx.persistence.repository import Repository, RepositoryError
    from veritycx.providers.deterministic import DeterministicProvider
    from veritycx.service.configuration import Settings
    from veritycx.service.runtime import run_async

    async def exercise() -> None:
        """Restore a missing checkpoint identifier and inspect the terminal failure guard."""
        manifest, _ = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner = uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            await repo.accept(
                owner, parent.id, uuid4(), "What is the Alder savings opening deposit?"
            )
            async with pool.connection() as conn:
                await conn.execute(
                    "UPDATE support_app.jobs SET checkpoint_id='missing-checkpoint' "
                    "WHERE conversation_id=%s",
                    (parent.id,),
                )
            job = await repo.claim(uuid4(), conversation_id=parent.id)
            assert job is not None
            await process_job(pool, job, Settings(), DeterministicProvider())
            with pytest.raises(RepositoryError, match="incompatible_state"):
                await repo.accept(owner, parent.id, uuid4(), "New question")

    run_async(exercise())
