"""Provide bounded async pools with fixed schema paths and short explicit transactions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from veritycx.persistence.migrate import verify_schema

type DatabaseConnection = AsyncConnection[dict[str, object]]
type DatabasePool = AsyncConnectionPool[DatabaseConnection]


async def configure_connection(conn: DatabaseConnection) -> None:
    """Fix the saver schema and validate readiness without runtime DDL."""
    await conn.execute("SET search_path TO support_checkpoints, pg_catalog")
    await verify_schema(conn)


@asynccontextmanager
async def database_pool(dsn: str, *, max_size: int = 20) -> AsyncIterator[DatabasePool]:
    """Open a bounded verified pool; propagate unavailable storage to the caller."""
    if not 1 <= max_size <= 20:
        raise ValueError("invalid_pool_size")
    pool: DatabasePool = AsyncConnectionPool(
        dsn,
        min_size=1,
        max_size=max_size,
        open=False,
        timeout=5,
        kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 5},
        configure=configure_connection,
    )
    try:
        await pool.open(wait=True, timeout=5)
        yield pool
    finally:
        await pool.close()


@asynccontextmanager
async def transaction(pool: DatabasePool) -> AsyncIterator[DatabaseConnection]:
    """Borrow one connection for one atomic unit, rolling back on any exception."""
    async with pool.connection() as conn, conn.transaction():
        yield conn
