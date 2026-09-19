"""Check shared async startup creates a Selector loop before coroutine execution."""

import asyncio
import sys

from veritycx.service.runtime import run_async


def test_async_entrypoint() -> None:
    """All launchers must use this helper before opening Psycopg connections."""

    async def inspect_loop() -> bool:
        """Inspect the running loop inside the launched coroutine."""
        loop = asyncio.get_running_loop()
        return sys.platform != "win32" or isinstance(loop, asyncio.SelectorEventLoop)

    assert run_async(inspect_loop())
