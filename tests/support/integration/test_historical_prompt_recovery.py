"""Keep completed historical answers and unknown provenance intact across recovery."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from veritycx.conversations.models import TurnResult
from veritycx.observability.audit import commit_result, export_result
from veritycx.observability.export import TraceExporter
from veritycx.orchestration.rag import create_rag
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.protocol import ProviderRequest, ProviderResult
from veritycx.providers.rewrite import RewriteRequest, RewriteResult
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


class ForbiddenProviders:
    """Fail immediately if terminal recovery tries either provider again."""

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """A completed historical result must not spend an answer attempt."""
        raise AssertionError("unexpected historical answer call")

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """A completed historical result must not spend a rewrite attempt."""
        raise AssertionError("unexpected historical rewrite call")


def test_completed_historical_recovery_exports_unchanged_unknown_prompt(
    test_database_url: str,
) -> None:
    """A newer worker reclaims unfinished work without relabeling retained history."""

    async def exercise() -> None:
        captured: list[dict[str, object]] = []

        def capture(request: httpx.Request) -> httpx.Response:
            """Intercept the real exporter at the network boundary."""
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={})

        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            parent = await repo.create(uuid4(), uuid4(), "historical-v2")
            turn = await repo.accept(
                parent.owner_id, parent.id, uuid4(), "Historical synthetic question"
            )
            old = await repo.claim(uuid4(), conversation_id=parent.id)
            assert old is not None
            expected = TurnResult(kind="abstain", text="Historical fixture result.")
            await commit_result(pool, old, expected, "knowledge")
            async with pool.connection() as conn:
                before = await (
                    await conn.execute(
                        "SELECT * FROM support_app.audit WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
                await conn.execute(
                    "UPDATE support_app.jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
                    (old.id,),
                )
            current = await repo.claim(uuid4(), conversation_id=parent.id)
            assert current is not None and current.fence > old.fence
            forbidden = ForbiddenProviders()
            rag = create_rag(forbidden)
            try:
                await process_job(pool, current, Settings(), forbidden, rag=rag)
            finally:
                rag.inference.close()
            async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as client:
                await export_result(
                    pool,
                    current,
                    TraceExporter(client, SecretStr("offline-placeholder"), "fixture"),
                    "openai",
                )
            async with pool.connection() as conn:
                after = await (
                    await conn.execute(
                        "SELECT * FROM support_app.audit WHERE turn_id=%s", (turn.id,)
                    )
                ).fetchone()
                stored = await (
                    await conn.execute(
                        "SELECT result FROM support_app.turns WHERE id=%s", (turn.id,)
                    )
                ).fetchone()
                job = await (
                    await conn.execute(
                        "SELECT status FROM support_app.jobs WHERE id=%s", (current.id,)
                    )
                ).fetchone()
            assert before == after and after is not None and after["prompt_version"] is None
            assert stored is not None and stored["result"] == expected.model_dump(mode="json")
            assert job is not None and job["status"] == "completed"
            assert len(captured) == 1
            assert captured[0]["inputs"] == {} and captured[0]["outputs"] == {}
            extra = captured[0]["extra"]
            assert isinstance(extra, dict) and extra["metadata"]["prompt_version"] == "unknown"

    run_async(exercise())
