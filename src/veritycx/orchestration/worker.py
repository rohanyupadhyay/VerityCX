"""Run bounded durable jobs with independent lease renewal and content-free heartbeats."""

import argparse
import asyncio
import os
from pathlib import Path
from uuid import uuid4

import httpx
from openai import AsyncOpenAI
from psycopg import Error
from psycopg_pool import PoolTimeout

from veritycx.environment import EnvironmentLoadError, load_project_environment
from veritycx.handoff.bridge import run_bridge
from veritycx.knowledge.configuration import active_corpus
from veritycx.knowledge.resources import ResourceError
from veritycx.observability.audit import export_result
from veritycx.observability.export import TraceExporter
from veritycx.orchestration.graph import execute_job
from veritycx.orchestration.rag import RAGServices, create_rag, deterministic_rag
from veritycx.orchestration.recovery import block_incompatible, reconcile_terminal
from veritycx.persistence.database import DatabasePool, database_pool
from veritycx.persistence.maintenance import purge_expired
from veritycx.persistence.migrate import MigrationError
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.policy.sources import SourceError
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.providers.openai import OpenAIProvider
from veritycx.providers.protocol import KnowledgeProvider
from veritycx.providers.rewrite import OpenAIQueryRewriter
from veritycx.service.configuration import (
    ConfigurationError,
    RuntimeConfiguration,
    Settings,
    load_configuration,
)
from veritycx.service.runtime import run_async


async def process_job(
    pool: DatabasePool,
    job: WorkJob,
    settings: Settings,
    provider: KnowledgeProvider,
    *,
    rag: RAGServices,
) -> None:
    """Cancel processing if its lease renewal loses authority; finish only reconciled work."""
    repository = Repository(pool)
    if await reconcile_terminal(pool, job):
        return

    async def renew() -> None:
        """Keep the current lease alive at the fixed five-second cadence."""
        while True:
            await asyncio.sleep(settings.heartbeat_seconds)
            await repository.renew(job)

    renewal = asyncio.create_task(renew())
    execution = asyncio.create_task(execute_job(pool, job, settings, provider, rag=rag))
    try:
        done, _ = await asyncio.wait({renewal, execution}, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            await task
        if job.kind != "resume":
            await repository.finish(job)
    except RepositoryError as error:
        if str(error) == "incompatible_state":
            await block_incompatible(pool, job)
        else:
            raise
    finally:
        renewal.cancel()
        execution.cancel()
        await asyncio.gather(renewal, execution, return_exceptions=True)


async def work(
    configuration: RuntimeConfiguration,
    provider: KnowledgeProvider,
    exporter: TraceExporter | None = None,
    *,
    rag: RAGServices,
) -> None:
    """Poll accepted/expired work every second, limiting concurrency to configured slots."""
    worker = uuid4()
    async with database_pool(
        configuration.database_url.get_secret_value(), max_size=configuration.settings.pool_max_size
    ) as pool:
        repository = Repository(pool)

        async def execute(job: WorkJob) -> None:
            """Complete durable work before isolated optional metadata export."""
            await process_job(pool, job, configuration.settings, provider, rag=rag)
            if exporter is not None:
                try:
                    await export_result(pool, job, exporter, configuration.settings.provider)
                except (Error, PoolTimeout):
                    exporter.failures += 1

        running: set[asyncio.Task[None]] = set()
        tick = 0
        await purge_expired(pool)
        bridge = (
            asyncio.create_task(run_bridge(pool, configuration.chatwoot, configuration.settings))
            if configuration.chatwoot is not None
            else None
        )
        try:
            while True:
                if bridge is not None and bridge.done():
                    # A failed bridge must stop worker readiness instead of silently losing chat.
                    await bridge
                if tick and tick % configuration.settings.purge_interval_seconds == 0:
                    await purge_expired(pool)
                if tick % configuration.settings.heartbeat_seconds == 0:
                    await repository.heartbeat(worker)
                for task in tuple(running):
                    if task.done():
                        running.remove(task)
                        try:
                            await task
                        except RepositoryError:
                            # A failed authority/restore guard leaves durable evidence for recovery.
                            print("worker_job_blocked")
                while len(running) < configuration.settings.worker_concurrency:
                    job = await repository.claim(worker)
                    if job is None:
                        break
                    running.add(asyncio.create_task(execute(job)))
                await asyncio.sleep(configuration.settings.work_scan_seconds)
                tick += 1
        finally:
            if bridge is not None:
                bridge.cancel()
                await asyncio.gather(bridge, return_exceptions=True)
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)


async def configured_worker(configuration: RuntimeConfiguration) -> None:
    """Create an explicit exporter only when opted in; ignore ambient trace endpoints."""
    async with httpx.AsyncClient(trust_env=False) as client:
        exporter = None
        if configuration.settings.traces_enabled:
            if configuration.trace_key is None or configuration.trace_project is None:
                raise ConfigurationError("missing_trace_configuration")
            exporter = TraceExporter(client, configuration.trace_key, configuration.trace_project)
        await run_configured_provider(configuration, exporter)


async def run_configured_provider(
    configuration: RuntimeConfiguration, exporter: TraceExporter | None
) -> None:
    """Select exactly one provider; missing live credentials never trigger fixture fallback."""
    if configuration.settings.provider == "deterministic":
        rag = await asyncio.to_thread(deterministic_rag)
        await asyncio.to_thread(active_corpus, configuration.settings.corpus_mode)
        await work(configuration, DeterministicProvider(), exporter, rag=rag)
        return
    if configuration.provider_key is None:
        raise ConfigurationError("missing_provider_credential")
    async with AsyncOpenAI(
        api_key=configuration.provider_key.get_secret_value(), max_retries=0
    ) as client:
        rag = await asyncio.to_thread(
            create_rag, OpenAIQueryRewriter(client, configuration.settings.effective_rewrite_model)
        )
        await asyncio.to_thread(active_corpus, configuration.settings.corpus_mode)
        await work(
            configuration, OpenAIProvider(client, configuration.settings.model), exporter, rag=rag
        )


def main() -> int:
    """Start a single worker on the shared Windows-compatible loop."""
    try:
        load_project_environment()
    except EnvironmentLoadError as error:
        print(str(error))
        return 1
    parser = argparse.ArgumentParser(description="Run local support worker")
    parser.add_argument("--provider", choices=["deterministic", "openai"])
    parser.add_argument("--corpus-mode", choices=["synthetic", "official"])
    args = parser.parse_args()
    try:
        configuration = load_configuration(
            Path("config/support.toml"),
            os.environ,
            provider=args.provider,
            corpus_mode=args.corpus_mode,
        )
        run_async(configured_worker(configuration))
    except ConfigurationError as error:
        print(str(error))
        return 1
    except MigrationError as error:
        print(str(error))
        return 1
    except (ResourceError, SourceError) as error:
        print(str(error))
        return 1
    except (Error, PoolTimeout):
        print("worker_storage_unavailable")
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
