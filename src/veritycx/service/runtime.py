"""Run async entry points on a Psycopg-compatible loop before any connections exist."""

import asyncio
from collections.abc import Coroutine


def run_async[T](coroutine: Coroutine[None, None, T]) -> T:
    """Run and close a Selector event loop, propagating application failures."""
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(coroutine)
