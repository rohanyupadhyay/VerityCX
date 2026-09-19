"""Guard every asynchronous saver write and pointer publication in one connection transaction."""

import asyncio
import math
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Interrupt

from veritycx.persistence.database import DatabaseConnection
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import RepositoryError, worker_guard


def restricted_serializer() -> JsonPlusSerializer:
    """Allow framework primitives and Interrupt without application imports or pickle."""
    return JsonPlusSerializer(
        pickle_fallback=False, allowed_json_modules=[], allowed_msgpack_modules=[]
    )


def validate_primitive(value: object, depth: int = 0) -> None:
    """Bound nesting and forbid arbitrary objects before serializer dispatch."""
    if depth > 30:
        raise RepositoryError("incompatible_state")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, Interrupt):
        validate_primitive(value.value, depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            validate_primitive(item, depth + 1)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            validate_primitive(item, depth + 1)
        return
    raise RepositoryError("incompatible_state")


def validate_checkpoint(
    checkpoint: Checkpoint, conversation: UUID, job: UUID, corpus: str, origin: UUID | None = None
) -> None:
    """Validate envelope primitives and bind the saved state to its originating job."""
    validate_primitive(checkpoint)
    if checkpoint.get("v") not in {2, 4}:
        raise RepositoryError("incompatible_state")
    values = checkpoint["channel_values"]
    state: object = values.get("__start__", values)
    if not isinstance(state, dict):
        raise RepositoryError("incompatible_state")
    application_keys = {
        "schema_version",
        "conversation_id",
        "job_id",
        "turn_id",
        "corpus_version",
        "route",
        "evidence_ids",
        "provider_result_id",
        "pause_id",
        "input_context",
    }
    if any(
        key not in application_keys and not key.startswith(("__", "branch:to:")) for key in state
    ):
        raise RepositoryError("incompatible_state")
    for key in ("route", "turn_id", "provider_result_id", "pause_id"):
        if key in state and state[key] is not None and not isinstance(state[key], str):
            raise RepositoryError("incompatible_state")
    if "evidence_ids" in state:
        evidence = state["evidence_ids"]
        if (
            not isinstance(evidence, list)
            or len(evidence) > 6
            or any(not isinstance(x, str) for x in evidence)
        ):
            raise RepositoryError("incompatible_state")
    if (
        type(state.get("schema_version")) is not int
        or state.get("schema_version") != 1
        or state.get("conversation_id") != str(conversation)
        or state.get("job_id") not in {str(job), str(origin) if origin else str(job)}
        or state.get("corpus_version") != corpus
    ):
        raise RepositoryError("incompatible_state")


class GuardedSaver(BaseCheckpointSaver[int]):
    """Wrap a borrowed connection, never a pool, for one trusted worker execution."""

    def __init__(
        self, conn: DatabaseConnection, job: WorkJob, corpus: str, origin: UUID | None = None
    ) -> None:
        """Bind immutable worker authority and use restricted serialization."""
        super().__init__(serde=restricted_serializer())
        self._guard_lock = asyncio.Lock()
        self.conn = conn
        self.job = job
        self.corpus = corpus
        self.origin = origin
        self.delegate = AsyncPostgresSaver(conn, serde=self.serde)

    def validate_config(self, config: RunnableConfig) -> None:
        """Refuse caller-selected foreign threads and arbitrary namespaces."""
        values = config.get("configurable", {})
        if (
            values.get("thread_id") != str(self.job.conversation_id)
            or values.get("checkpoint_ns", "") != ""
        ):
            raise RepositoryError("incompatible_state")

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save checkpoint/blobs and publish its approved pointer atomically."""
        self.validate_config(config)
        validate_checkpoint(
            checkpoint, self.job.conversation_id, self.job.id, self.corpus, self.origin
        )
        validate_primitive(metadata)
        async with self._guard_lock, self.conn.transaction():
            parent = await worker_guard(self.conn, self.job)
            if parent.corpus_version != self.corpus:
                raise RepositoryError("incompatible_state")
            result = await self.delegate.aput(config, checkpoint, metadata, new_versions)
            await self.conn.execute(
                "UPDATE support_app.jobs SET checkpoint_id=%s,checkpoint_ns='' WHERE id=%s",
                (checkpoint["id"], self.job.id),
            )
            return result

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, object]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Protect pending writes with the same parent/fence transaction as checkpoint writes."""
        self.validate_config(config)
        validate_primitive(tuple(writes))
        async with self._guard_lock, self.conn.transaction():
            await worker_guard(self.conn, self.job)
            await self.delegate.aput_writes(config, writes, task_id, task_path)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Restore only the current approved pointer and validate application binding."""
        self.validate_config(config)
        async with self._guard_lock, self.conn.transaction():
            await worker_guard(self.conn, self.job)
            cursor = await self.conn.execute(
                "SELECT checkpoint_id FROM support_app.jobs WHERE id=%s", (self.job.id,)
            )
            row = await cursor.fetchone()
            pointer = row.get("checkpoint_id") if row else None
            requested = config.get("configurable", {}).get("checkpoint_id")
            if requested is not None and requested != pointer:
                raise RepositoryError("incompatible_state")
            if pointer is None:
                return None
            if not isinstance(pointer, str):
                raise RepositoryError("incompatible_state")
            approved: RunnableConfig = {
                "configurable": {
                    "thread_id": str(self.job.conversation_id),
                    "checkpoint_ns": "",
                    "checkpoint_id": pointer,
                }
            }
            result = await self.delegate.aget_tuple(approved)
            if result is None:
                raise RepositoryError("incompatible_state")
            validate_checkpoint(
                result.checkpoint, self.job.conversation_id, self.job.id, self.corpus, self.origin
            )
            validate_primitive(result.pending_writes)
            return result

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, object] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Expose only an authorized approved snapshot, never arbitrary thread history."""
        if config is None or filter is not None or before is not None:
            raise RepositoryError("incompatible_state")
        if limit is not None and limit <= 0:
            return
        result = await self.aget_tuple(config)
        if result is not None:
            yield result

    async def adelete_thread(self, thread_id: str) -> None:
        """Deny worker deletion; retention must use the separate maintenance guard."""
        raise RepositoryError("maintenance_required")
