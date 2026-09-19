"""Distinguish process liveness from durable service readiness without exposing configuration."""

from pathlib import Path

import httpx
from pydantic import SecretStr

from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async


def test_health_without_storage(tmp_path: Path) -> None:
    """Health needs no bearer token; an uninitialized pool cannot claim readiness."""
    auth, _, _ = init_demo(tmp_path)
    config = RuntimeConfiguration(Settings(), SecretStr("secret-canary"), auth)
    app = create_app(config)

    async def exercise() -> None:
        """Exercise the ASGI boundary without opening a database connection."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            live = await client.get("/health/live")
            ready = await client.get("/health/ready")
            assert live.status_code == 200 and live.json() == {"status": "alive"}
            assert ready.status_code == 503 and ready.json() == {"status": "not_ready"}
            assert "secret-canary" not in ready.text

    run_async(exercise())
