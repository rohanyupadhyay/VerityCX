"""Verify authentication and sanitized input handling at the HTTP boundary."""

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async


def test_auth_precedes_storage(tmp_path: Path) -> None:
    """Anonymous access must fail without accepting work or exposing storage details."""
    auth, _, _ = init_demo(tmp_path)
    configuration = RuntimeConfiguration(
        Settings(), SecretStr("host=127.0.0.1 port=1 dbname=unavailable"), auth
    )

    async def exercise() -> None:
        """Call the ASGI app through an offline transport without external sockets."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(configuration)), base_url="http://test"
        ) as client:
            response = await client.post("/conversations", json={"schema_version": 1})
            assert response.status_code == 401
            assert "host=" not in response.text

    run_async(exercise())


@pytest.mark.support_db
def test_durable_http_flow(tmp_path: Path, test_database_url: str) -> None:
    """Create, accept, execute and poll actual durable rows with isolation and strict input."""
    from uuid import uuid4

    from veritycx.knowledge.configuration import source_mode
    from veritycx.knowledge.manifest import approve, prepare
    from veritycx.orchestration.worker import process_job
    from veritycx.persistence.database import database_pool
    from veritycx.persistence.repository import Repository
    from veritycx.providers.deterministic import DeterministicProvider, fixture_cases

    root, cache, pin = source_mode("synthetic")
    manifest = prepare(root, cache, "synthetic", pin)
    approve(root, cache, manifest.aggregate_hash)
    auth, first, second = init_demo(tmp_path)
    config = RuntimeConfiguration(Settings(), SecretStr(test_database_url), auth)
    app = create_app(config)

    async def exercise() -> None:
        """Use the actual ASGI routes and worker graph with one shared native database."""
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            headers = {
                "Authorization": "Bearer " + first.read_text().strip(),
                "Idempotency-Key": str(uuid4()),
            }
            created = await client.post(
                "/conversations", json={"schema_version": 1}, headers=headers
            )
            assert created.status_code == 201, created.text
            target = created.json()["conversation_id"]
            headers["Idempotency-Key"] = str(uuid4())
            accepted = await client.post(
                f"/conversations/{target}/turns",
                headers=headers,
                json={"schema_version": 1, "message": fixture_cases()[0].question},
            )
            assert accepted.status_code == 202, accepted.text
            repeated = await client.post(
                f"/conversations/{target}/turns",
                headers=headers,
                json={"schema_version": 1, "message": fixture_cases()[0].question},
            )
            assert repeated.json()["turn_id"] == accepted.json()["turn_id"]
            from uuid import UUID

            async with database_pool(test_database_url) as pool:
                repo = Repository(pool)
                job = await repo.claim(uuid4(), conversation_id=UUID(target))
                assert job is not None
                await process_job(pool, job, Settings(), DeterministicProvider())
            polled = await client.get(f"/conversations/{target}", headers=headers)
            assert polled.status_code == 200
            turn = polled.json()["turns"][0]
            assert turn["status"] == "completed"
            assert turn["result"]["kind"] == "answer"
            assert turn["result"]["citations"][0]["document_id"] == "policy-01"
            foreign = {"Authorization": "Bearer " + second.read_text().strip()}
            assert (
                await client.get(f"/conversations/{target}", headers=foreign)
            ).status_code == 404
            assert (
                await client.get(f"/conversations/{uuid4()}", headers=foreign)
            ).status_code == 404
            for body in [
                b'{"schema_version":1,"schema_version":1,"message":"x"}',
                b'{"schema_version":1,"message":"x","owner_id":"forged"}',
            ]:
                assert (
                    await client.post(
                        f"/conversations/{target}/turns", headers=headers, content=body
                    )
                ).status_code == 422
            oversized = await client.post(
                f"/conversations/{target}/turns", headers=headers, content=b"x" * 65537
            )
            assert oversized.status_code == 413

    run_async(exercise())
