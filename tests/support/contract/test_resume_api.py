"""Reject stale, foreign, implicit or arbitrary graph resume inputs."""

from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from veritycx.conversations.models import ConversationView, ResumeInput
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.repository import Repository
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async


@pytest.mark.parametrize(
    "extra",
    [
        {"goto": "knowledge"},
        {"update": {"owner": "foreign"}},
        {"thread_id": "foreign"},
        {"continue_automation": False},
    ],
)
def test_resume_payload(extra: dict[str, object]) -> None:
    """Only explicit consent, current pause and current revision are accepted as input."""
    value: dict[str, object] = {
        "schema_version": 1,
        "pause_id": str(uuid4()),
        "expected_revision": 1,
        "continue_automation": True,
    }
    value.update(extra)
    with pytest.raises(ValidationError):
        ResumeInput.model_validate(value)


@pytest.mark.support_db
@pytest.mark.parametrize("corrupt", [False, True])
def test_resume_http_projection(tmp_path: Path, test_database_url: str, corrupt: bool) -> None:
    """Keep pause delivery truthful and expose the same durable resume across retries."""
    auth, first, second = init_demo(tmp_path)
    app = create_app(RuntimeConfiguration(Settings(), SecretStr(test_database_url), auth))

    async def exercise() -> None:
        """Drive authenticated endpoints and execute only their accepted database jobs."""
        async with (
            app.router.lifespan_context(app),
            database_pool(test_database_url) as pool,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            headers = {
                "Authorization": "Bearer " + first.read_text().strip(),
                "Idempotency-Key": str(uuid4()),
            }
            created = await client.post(
                "/conversations", headers=headers, json={"schema_version": 1}
            )
            target = created.json()["conversation_id"]
            url = f"/conversations/{target}"
            headers["Idempotency-Key"] = str(uuid4())
            assert (
                await client.post(
                    url + "/turns",
                    headers=headers,
                    json={"schema_version": 1, "message": "I want a human agent"},
                )
            ).status_code == 202
            repo = Repository(pool)
            job = await repo.claim(uuid4(), conversation_id=UUID(target))
            assert job is not None
            await process_job(pool, job, Settings(), DeterministicProvider())
            view = ConversationView.model_validate_json(
                (await client.get(url, headers=headers)).content
            )
            assert view.escalation and view.escalation.delivery == "not_connected"
            payload = {
                "schema_version": 1,
                "pause_id": view.escalation.pause_id,
                "expected_revision": view.revision,
                "continue_automation": True,
            }
            foreign = {
                "Authorization": "Bearer " + second.read_text().strip(),
                "Idempotency-Key": str(uuid4()),
            }
            assert (
                await client.post(url + "/resume", headers=foreign, json=payload)
            ).status_code == 404
            headers["Idempotency-Key"] = str(uuid4())
            assert (
                await client.post(
                    url + "/resume",
                    headers=headers,
                    json={**payload, "expected_revision": view.revision + 1},
                )
            ).status_code == 409
            response = await client.post(url + "/resume", headers=headers, json=payload)
            assert response.status_code == 202 and response.json()["status"] == "accepted"
            assert (
                await client.post(url + "/resume", headers=headers, json=payload)
            ).json() == response.json()
            pending = ConversationView.model_validate_json(
                (await client.get(url, headers=headers)).content
            )
            assert pending.status == "escalation_pending" and pending.escalation is None
            assert (
                pending.latest_resume_operation
                and pending.latest_resume_operation.status == "accepted"
            )
            job = await repo.claim(uuid4(), conversation_id=UUID(target))
            assert job is not None
            if corrupt:
                async with pool.connection() as conn:
                    await conn.execute(
                        "UPDATE support_app.jobs SET checkpoint_id='missing' WHERE id=%s", (job.id,)
                    )
            await process_job(pool, job, Settings(), DeterministicProvider())
            completed = ConversationView.model_validate_json(
                (await client.get(url, headers=headers)).content
            )
            if corrupt:
                assert completed.status == "escalation_pending" and completed.escalation is None
                assert (
                    completed.latest_resume_operation and completed.latest_resume_operation.failure
                )
                assert completed.latest_resume_operation.failure.code == "incompatible_state"
                denied = await client.post(
                    url + "/resume",
                    headers={**headers, "Idempotency-Key": str(uuid4())},
                    json=payload,
                )
                assert denied.status_code == 503
                retry = await client.post(url + "/resume", headers=headers, json=payload)
                assert (
                    retry.status_code == 202
                    and retry.json()["failure"]["recovery"] == "operator_required"
                )
                return
            assert completed.status == "active" and completed.latest_resume_operation
            assert completed.latest_resume_operation.status == "completed"
            assert (await client.post(url + "/resume", headers=headers, json=payload)).json()[
                "status"
            ] == "completed"

    run_async(exercise())
