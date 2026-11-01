"""Bound physical blocking work even after its awaiting graph task has timed out."""

import asyncio
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from threading import Lock


class InferenceCapacityError(ValueError):
    """Report exhausted physical inference capacity without scheduling more threads."""


class InferenceCapacity:
    """Keep abandoned work charged until the underlying thread actually finishes."""

    def __init__(self, limit: int = 10) -> None:
        """Create a bounded process-owned executor, independent of any event loop."""
        if not 1 <= limit <= 10:
            raise ValueError("invalid_inference_capacity")
        self.limit = limit
        self._executor = ThreadPoolExecutor(max_workers=limit, thread_name_prefix="veritycx-nlp")
        self._lock = Lock()
        self._active: set[object] = set()
        self._abandoned: set[object] = set()
        self._closed = False

    @property
    def available_slots(self) -> int:
        """Subtract abandoned physical work from the worker's schedulable job limit."""
        with self._lock:
            return 0 if self._closed else self.limit - len(self._abandoned)

    def _release(self, ticket: object) -> None:
        """Release a ticket only on physical completion or a cancelled queued future."""
        with self._lock:
            self._active.discard(ticket)
            self._abandoned.discard(ticket)

    async def run[T](self, operation: Callable[[], T]) -> T:
        """Await shielded blocking work while retaining capacity after cancellation."""
        ticket = object()
        with self._lock:
            if self._closed or len(self._active) >= self.limit:
                raise InferenceCapacityError("nlp_capacity_unavailable")
            self._active.add(ticket)
        context = copy_context()

        def execute() -> T:
            """Release capacity in the actual thread rather than the cancelled coroutine."""
            try:
                return context.run(operation)
            finally:
                self._release(ticket)

        try:
            future = self._executor.submit(execute)
        except RuntimeError:
            self._release(ticket)
            raise InferenceCapacityError("nlp_capacity_unavailable") from None

        def queued_cancelled(done: Future[T]) -> None:
            """A future cancelled before execution has no physical work left to charge."""
            if done.cancelled():
                self._release(ticket)

        future.add_done_callback(queued_cancelled)
        wrapped = asyncio.wrap_future(future)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            with self._lock:
                if ticket in self._active:
                    self._abandoned.add(ticket)

            def consume(done: asyncio.Future[T]) -> None:
                """Retrieve abandoned failures without logging customer input or raw errors."""
                if not done.cancelled():
                    done.exception()

            wrapped.add_done_callback(consume)
            raise

    def close(self) -> None:
        """Cancel queued work; running work remains charged until its own completion."""
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
