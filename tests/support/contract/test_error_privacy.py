"""Ensure unexpected internal exceptions never escape as response or server diagnostics."""

from pathlib import Path

import httpx
from pydantic import SecretStr

from veritycx.service.app import create_app
from veritycx.service.auth import init_demo
from veritycx.service.configuration import RuntimeConfiguration, Settings
from veritycx.service.runtime import run_async


def test_unexpected_error_is_sanitized(tmp_path: Path) -> None:
    """Exercise an actual ASGI error with a private exception canary and no database."""
    auth, _, _ = init_demo(tmp_path)
    app = create_app(RuntimeConfiguration(Settings(), SecretStr("unused"), auth))

    @app.get("/test-fault")
    async def fault() -> None:
        """Inject an unexpected internal exception only in this test application."""
        raise RuntimeError("PRIVATE_EXCEPTION_CANARY")

    async def exercise() -> None:
        """Require the transport to receive a normalized response rather than rethrowing."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/test-fault")
            assert response.status_code == 500
            assert "PRIVATE_EXCEPTION_CANARY" not in response.text
            assert response.json()["error"]["code"] == "internal_error"

    run_async(exercise())
