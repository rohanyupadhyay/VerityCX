"""Expose content-free liveness/readiness with durable worker and cleanup prerequisites."""

from collections.abc import Callable

from fastapi import FastAPI
from psycopg import Error
from psycopg_pool import PoolTimeout
from starlette.responses import JSONResponse

from veritycx.knowledge.configuration import active_corpus
from veritycx.persistence.database import DatabasePool
from veritycx.persistence.migrate import MigrationError, verify_schema
from veritycx.policy.sources import SourceError
from veritycx.service.configuration import Settings
from veritycx.service.routes import ServiceError


def register_health(
    app: FastAPI, settings: Settings, pool_getter: Callable[[], DatabasePool]
) -> None:
    """Register health handlers without credentials, content or provider network probes."""

    @app.get("/health/live")
    async def live() -> JSONResponse:
        """Report only that this process is accepting HTTP requests."""
        return JSONResponse({"status": "alive"})

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        """Require valid storage/corpus, a fresh worker heartbeat and no overdue purge."""
        healthy = False
        try:
            active_corpus(settings.corpus_mode)
            async with pool_getter().connection() as conn:
                await verify_schema(conn)
                cursor = await conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM support_app.worker_heartbeats "
                    "WHERE last_seen>clock_timestamp()-interval '15 seconds') AND NOT EXISTS "
                    "(SELECT 1 FROM support_app.conversations WHERE "
                    "expires_at<clock_timestamp()-interval '24 hours' OR "
                    "deleted_at<clock_timestamp()-interval '24 hours') AS ready"
                )
                row = await cursor.fetchone()
                healthy = row is not None and row.get("ready") is True
        except (Error, PoolTimeout, MigrationError, SourceError, ServiceError):
            healthy = False
        return JSONResponse(
            {"status": "ready" if healthy else "not_ready"}, status_code=200 if healthy else 503
        )
