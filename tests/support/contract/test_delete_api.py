"""Verify owner-authorized deletion, retained identical acknowledgments and immediate denial."""

from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from veritycx.knowledge.configuration import source_mode
from veritycx.knowledge.manifest import approve, prepare
from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async

pytestmark = pytest.mark.support_db


def test_delete_api(tmp_path: Path, test_database_url: str) -> None:
    """A foreign owner cannot delete; an authorized repeated delete never reveals content."""
    root, cache, pin = source_mode("synthetic")
    manifest = prepare(root, cache, "synthetic", pin)
    approve(root, cache, manifest.aggregate_hash)
    auth, first, second = init_demo(tmp_path)
    app = create_app(RuntimeConfiguration(Settings(), SecretStr(test_database_url), auth))

    async def exercise() -> None:
        """Call the actual ASGI endpoints against dedicated native storage."""
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
                "/conversations", headers=headers, json={"schema_version": 1}
            )
            target = created.json()["conversation_id"]
            foreign = {
                "Authorization": "Bearer " + second.read_text().strip(),
                "Idempotency-Key": str(uuid4()),
            }
            assert (
                await client.delete(f"/conversations/{target}", headers=foreign)
            ).status_code == 404
            headers["Idempotency-Key"] = str(uuid4())
            deleted = await client.delete(f"/conversations/{target}", headers=headers)
            assert deleted.status_code == 202 and deleted.content == b""
            assert (
                await client.delete(f"/conversations/{target}", headers=headers)
            ).status_code == 202
            assert (
                await client.get(f"/conversations/{target}", headers=headers)
            ).status_code == 404

    run_async(exercise())
