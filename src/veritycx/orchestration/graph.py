"""Execute a knowledge-only graph while application rows remain authoritative."""

from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context

from veritycx.conversations.models import TurnResult
from veritycx.knowledge.configuration import active_corpus
from veritycx.knowledge.retrieval import recent_context, retrieve
from veritycx.observability.audit import commit_result
from veritycx.orchestration.router import route_intent
from veritycx.orchestration.state import ConversationState
from veritycx.persistence.attempts import AttemptLedger, BudgetError
from veritycx.persistence.checkpoints import GuardedSaver
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.escalations import (
    consumed_pause,
    ensure_pause,
    fail_resume,
    finalize_resume,
)
from veritycx.persistence.models import TurnRow, WorkJob
from veritycx.persistence.repository import RepositoryError, worker_guard
from veritycx.policy.outputs import validate_result
from veritycx.policy.sources import SourceError
from veritycx.providers.execution import invoke_provider
from veritycx.providers.protocol import (
    ContextMessage,
    KnowledgeProvider,
    ProviderError,
    ProviderRequest,
)
from veritycx.service.configuration import Settings


async def execute_job(
    pool: DatabasePool, job: WorkJob, settings: Settings, provider: KnowledgeProvider
) -> None:
    """Execute or restore one fenced graph; HTTP state and provider output grant no authority."""
    async with transaction(pool) as conn:
        parent = await worker_guard(conn, job)
        cursor = await conn.execute("SELECT * FROM support_app.turns WHERE id=%s", (job.turn_id,))
        turn = TurnRow.model_validate(await cursor.fetchone())
        cursor = await conn.execute(
            "SELECT correlation_id FROM support_app.audit WHERE turn_id=%s", (turn.id,)
        )
        audit = await cursor.fetchone()
        correlation = audit.get("correlation_id") if audit else None
        if not isinstance(correlation, UUID):
            raise RepositoryError("incompatible_state")
        cursor = await conn.execute(
            "SELECT * FROM support_app.turns WHERE conversation_id=%s "
            "AND sequence<%s AND status='completed' ORDER BY sequence",
            (parent.id, turn.sequence),
        )
        history = [TurnRow.model_validate(row) for row in await cursor.fetchall()]
    if turn.status in {"completed", "failed"} and (
        turn.result is None or turn.result.kind != "escalation"
    ):
        return
    context: list[ContextMessage] = []
    for previous in history:
        context.append(ContextMessage(role="user", text=previous.text))
        if previous.result:
            context.append(ContextMessage(role="assistant", text=previous.result.text))
    initial: ConversationState = {
        "schema_version": 1,
        "conversation_id": str(parent.id),
        "job_id": str(job.id),
        "turn_id": str(turn.id),
        "corpus_version": parent.corpus_version,
        "route": "pending",
        "evidence_ids": [],
        "provider_result_id": None,
        "pause_id": None,
        "input_context": [message.model_dump() for message in recent_context(context)],
    }

    async def security(state: ConversationState) -> ConversationState:
        """Recheck current database authority before any retrieval or provider execution."""
        async with transaction(pool) as connection:
            await worker_guard(connection, job)
        return state

    async def router(state: ConversationState) -> ConversationState:
        """Route accepted application input deterministically without any provider call."""
        return {**state, "route": route_intent(turn.text)}

    async def knowledge(state: ConversationState) -> ConversationState:
        """Retrieve only reviewed evidence and use the durable provider attempt ledger."""
        try:
            manifest, corpus = active_corpus(settings.corpus_mode)
            if manifest.corpus_version != parent.corpus_version:
                raise SourceError("corpus_changed")
            selected = retrieve(turn.text, corpus)
            if not selected:
                await commit_result(
                    pool,
                    job,
                    TurnResult(
                        kind="abstain", text="The approved sources do not support an answer."
                    ),
                    "knowledge",
                )
                return state
            request = ProviderRequest(
                correlation_id=str(correlation),
                question=turn.text,
                context=recent_context(context),
                evidence=tuple(selected),
                remaining_seconds=60.0,
            )
            result = await invoke_provider(provider, AttemptLedger(pool), job, request)
            await commit_result(pool, job, validate_result(request, result), "knowledge", result)
            return {
                **state,
                "evidence_ids": [item.section_id for item in selected],
                "provider_result_id": str(turn.id),
            }
        except (SourceError, ProviderError, BudgetError) as error:
            category = error.category if isinstance(error, ProviderError) else str(error)
            await commit_result(
                pool,
                job,
                TurnResult(
                    kind="error",
                    text=(
                        "An answer could not be completed. "
                        "You may submit a new question to try again."
                    ),
                    failure_category=category,
                ),
                "knowledge",
            )
            return state

    async def limited(state: ConversationState) -> ConversationState:
        """Explain unsupported intents without inventing an account action or human notification."""
        route = state["route"]
        if route == "clarify":
            result = TurnResult(
                kind="clarify", text="Please clarify the banking policy you want explained."
            )
        elif route == "human":
            result = TurnResult(
                kind="unavailable",
                text="Human escalation is not implemented yet. Nobody has been notified.",
            )
        else:
            result = TurnResult(
                kind="unavailable",
                text=(
                    "Account and transaction operations are unavailable. "
                    "No banking records were changed."
                ),
            )
        await commit_result(pool, job, result, route)
        return state

    async def human(state: ConversationState) -> ConversationState:
        """Persist a truthful pause and accept only a server-authorized continuation."""
        pause = (
            (await consumed_pause(pool, job))[0]
            if job.kind == "resume"
            else await ensure_pause(pool, job)
        )
        decision = interrupt({"pause_id": str(pause.pause_id), "delivery": "not_connected"})
        if job.kind != "resume" or decision != {
            "pause_id": str(pause.pause_id),
            "continue_automation": True,
        }:
            raise RepositoryError("incompatible_state")
        return {**state, "job_id": str(job.id), "route": "resumed", "pause_id": None}

    def branch(state: ConversationState) -> str:
        """Choose only a reviewed node; state cannot select arbitrary graph commands."""
        return state["route"] if state["route"] in {"knowledge", "human"} else "limited"

    graph = StateGraph(ConversationState)
    graph.add_node("security", security)
    graph.add_node("route", router)
    graph.add_node("knowledge", knowledge)
    graph.add_node("limited", limited)
    graph.add_node("human", human)
    graph.add_edge(START, "security")
    graph.add_edge("security", "route")
    graph.add_conditional_edges(
        "route", branch, {"knowledge": "knowledge", "limited": "limited", "human": "human"}
    )
    graph.add_edge("knowledge", END)
    graph.add_edge("limited", END)
    graph.add_edge("human", END)
    pause_origin = await consumed_pause(pool, job) if job.kind == "resume" else None
    async with pool.connection() as connection:
        saver = GuardedSaver(
            connection, job, parent.corpus_version, pause_origin[1] if pause_origin else None
        )
        with tracing_context(enabled=False):
            compiled = graph.compile(checkpointer=saver)
            config: RunnableConfig = {
                "configurable": {"thread_id": str(parent.id), "checkpoint_ns": ""}
            }
            if pause_origin:
                if not job.checkpoint_id:
                    await compiled.ainvoke(initial, config=config)
                snapshot = await compiled.aget_state(config)
                if snapshot.values.get("route") != "resumed":
                    if not snapshot.interrupts:
                        await fail_resume(pool, job)
                        return
                    expected = {
                        "pause_id": str(pause_origin[0].pause_id),
                        "delivery": "not_connected",
                    }
                    if len(snapshot.interrupts) != 1 or snapshot.interrupts[0].value != expected:
                        raise RepositoryError("incompatible_state")
                    await compiled.ainvoke(
                        Command(
                            resume={
                                "pause_id": str(pause_origin[0].pause_id),
                                "continue_automation": True,
                            }
                        ),
                        config=config,
                    )
                final = await compiled.aget_state(config)
                if final.next or final.interrupts or final.values.get("route") != "resumed":
                    raise RepositoryError("incompatible_state")
            else:
                await compiled.ainvoke(None if job.checkpoint_id else initial, config=config)
    if pause_origin:
        await finalize_resume(pool, job)
