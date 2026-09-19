"""Construct the local ASGI service with one bounded pool and sanitized error boundaries."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from psycopg import Error
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import ValidationError
from starlette.responses import JSONResponse, Response

from veritycx.persistence.database import DatabasePool, configure_connection
from veritycx.persistence.migrate import MigrationError
from veritycx.persistence.repository import RepositoryError
from veritycx.policy.sources import SourceError
from veritycx.service.auth import AuthError, load_principals
from veritycx.service.configuration import RuntimeConfiguration
from veritycx.service.health import register_health
from veritycx.service.routes import ServiceError, register_routes


def create_app(configuration: RuntimeConfiguration) -> FastAPI:
    """Create the app without connecting until lifespan startup; never execute runtime DDL."""
    principals = load_principals(configuration.auth_file)
    pool: DatabasePool | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Own one process pool; minimum zero keeps liveness available during a DB outage."""
        nonlocal pool
        pool = AsyncConnectionPool(
            configuration.database_url.get_secret_value(),
            min_size=0,
            max_size=configuration.settings.pool_max_size,
            open=False,
            timeout=5,
            kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 5},
            configure=configure_connection,
        )
        await pool.open()
        try:
            yield
        finally:
            await pool.close()
            pool = None

    def get_pool() -> DatabasePool:
        """Fail unavailable when the service lifecycle has not initialized its pool."""
        if pool is None:
            raise ServiceError("not_ready", 503)
        return pool

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    async def safe_error(request: Request, error: Exception) -> JSONResponse:
        """Normalize errors without reflecting SQL, paths, credentials or untrusted input."""
        status, code = 500, "internal_error"
        if isinstance(error, AuthError):
            status, code = 401, "unauthorized"
        elif isinstance(error, ServiceError):
            status, code = error.status, error.code
        elif isinstance(error, RepositoryError):
            code = str(error)
            status = 404 if code == "not_found" else 503 if code == "incompatible_state" else 409
        elif isinstance(error, (Error, PoolTimeout, MigrationError)):
            status, code = 503, "storage_unavailable"
        elif isinstance(error, SourceError):
            status, code = 503, "not_ready"
        elif isinstance(error, (ValueError, ValidationError)):
            status, code = 422, "invalid_input"
        return JSONResponse(
            {
                "schema_version": 1,
                "error": {
                    "code": code,
                    "retryable": code in {"busy", "storage_unavailable", "not_ready"},
                    "correlation_id": str(uuid4()),
                },
            },
            status_code=status,
        )

    for exception in (
        AuthError,
        ServiceError,
        RepositoryError,
        Error,
        PoolTimeout,
        MigrationError,
        SourceError,
        ValueError,
        ValidationError,
    ):
        app.add_exception_handler(exception, safe_error)

    @app.middleware("http")
    async def private_error_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Prevent unexpected exceptions reaching Uvicorn's raw traceback logger."""
        try:
            return await call_next(request)
        except Exception as error:
            return await safe_error(request, error)

    register_routes(app, configuration, principals, get_pool)
    register_health(app, configuration.settings, get_pool)
    return app
