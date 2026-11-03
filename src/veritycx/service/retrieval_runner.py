"""Exercise owned synthetic scenarios through the actual durable worker pipeline."""

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from psycopg.conninfo import conninfo_to_dict

from veritycx.conversations.models import TurnResult
from veritycx.knowledge.configuration import active_corpus
from veritycx.knowledge.models import CorpusManifest, EvidenceSection
from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.synonyms import WordNetExpander
from veritycx.orchestration.inference import InferenceCapacity
from veritycx.orchestration.rag import RAGServices
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import DatabasePool
from veritycx.persistence.models import WorkJob
from veritycx.persistence.repository import Repository
from veritycx.persistence.rewrites import RewriteRow
from veritycx.providers.protocol import ContextMessage
from veritycx.service.configuration import Settings
from veritycx.service.retrieval_cases import (
    RegressionError,
    RegressionScenario,
    RegressionSet,
    RegressionTurn,
    validate_case_sources,
)
from veritycx.service.retrieval_checks import (
    CallRecorder,
    ObservedTurn,
    RegressionRun,
    ScenarioResult,
    judge_turn,
)
from veritycx.service.retrieval_providers import ProviderFactory, RecordingAnswer, RecordingRewriter
from veritycx.service.validation import dedicated_database


def _failed_observation(
    case_id: str, turn: RegressionTurn, recorder: CallRecorder, start: float, error: str
) -> ObservedTurn:
    """Retain actual paid-call diagnostics when durable observations are unavailable."""
    return ObservedTurn(
        case_id=case_id,
        turn_id=turn.id,
        rewrite=next((r for r in reversed(recorder.rewrite_results) if r is not None), None),
        rewrite_requests=tuple(recorder.rewrite_requests),
        answer_requests=tuple(recorder.answer_requests),
        answer_results=tuple(recorder.answer_results),
        answer_attempts=len(recorder.answer_requests),
        elapsed_ms=int((monotonic() - start) * 1000),
        execution_error=error,
    )


async def _observe(
    pool: DatabasePool,
    job: WorkJob,
    case_id: str,
    turn: RegressionTurn,
    recorder: CallRecorder,
    sections: dict[str, EvidenceSection],
    elapsed_ms: int,
    error: str | None,
) -> ObservedTurn:
    """Read committed diagnostics and actual captured requests, never infer them from gold."""
    async with pool.connection() as conn:
        stored = await (
            await conn.execute("SELECT result FROM support_app.turns WHERE id=%s", (job.turn_id,))
        ).fetchone()
        raw = await (
            await conn.execute(
                "SELECT * FROM support_app.query_rewrites WHERE turn_id=%s", (job.turn_id,)
            )
        ).fetchone()
        attempts = await (
            await conn.execute(
                "SELECT count(*) AS count FROM support_app.attempts WHERE turn_id=%s",
                (job.turn_id,),
            )
        ).fetchone()
    result = (
        TurnResult.model_validate_json(json.dumps(stored["result"]))
        if stored and stored["result"]
        else None
    )
    row = RewriteRow.model_validate(raw) if raw else None
    selected = tuple(sections[i] for i in row.selected_source_ids if i in sections) if row else ()
    rewrite = next(
        (value for value in reversed(recorder.rewrite_results) if value is not None), None
    )
    count = attempts["count"] if attempts else 0
    if not isinstance(count, int):
        raise RegressionError("invalid_regression_observation")
    return ObservedTurn(
        case_id=case_id,
        turn_id=turn.id,
        result=result,
        rewrite=rewrite,
        rewrite_requests=tuple(recorder.rewrite_requests),
        answer_requests=tuple(recorder.answer_requests),
        answer_results=tuple(recorder.answer_results),
        rewrite_row=row,
        selected_sections=selected,
        answer_attempts=count,
        elapsed_ms=elapsed_ms,
        execution_error=error
        or (result.failure_category if result and result.kind == "error" else None),
    )


async def exercise_regressions(
    pool: DatabasePool,
    settings: Settings,
    scenarios: Sequence[RegressionScenario],
    *,
    manifest: CorpusManifest,
    evidence: Sequence[EvidenceSection],
    providers: ProviderFactory,
    mode: str,
) -> RegressionRun:
    """Run sequentially with scoped claims, fresh identities and unchanged inference budgets."""
    runtime = dedicated_database(os.environ.get("VERITYCX_DATABASE_URL", ""))
    if not isinstance(pool.conninfo, str) or conninfo_to_dict(
        dedicated_database(pool.conninfo)
    ) != conninfo_to_dict(runtime):
        raise RegressionError("invalid_regression_database")
    if mode not in {"offline", "live"}:
        raise RegressionError("invalid_regression_mode")
    case_set = RegressionSet(provenance="validated selection", scenarios=tuple(scenarios))
    validate_case_sources(case_set, manifest)
    current, current_sections = active_corpus("synthetic", validation=True)
    if manifest != current or {s.section_id: s for s in evidence} != {
        s.section_id: s for s in current_sections
    }:
        raise RegressionError("invalid_regression_corpus")
    catalog = manifest.catalog_index
    if catalog is None:
        raise RegressionError("invalid_regression_corpus")
    started_at = datetime.now(UTC).isoformat()
    normalizer = TextNormalizer()
    expander = WordNetExpander(normalizer)
    inference = InferenceCapacity(settings.worker_concurrency)
    repo = Repository(pool)
    results: list[ScenarioResult] = []
    sections = {s.section_id: s for s in evidence}
    try:
        for case in scenarios:
            owner = uuid4()
            parents: dict[str, UUID] = {}
            unavailable_parents: set[str] = set()
            histories: dict[str, list[ContextMessage]] = {alias: [] for alias in case.conversations}
            blocked: set[str] = set()
            observations = []
            for alias in case.conversations:
                try:
                    parent = await repo.create(owner, uuid4(), manifest.corpus_version)
                    parents[alias] = parent.id
                except Exception:
                    unavailable_parents.add(alias)
            for turn in case.turns:
                expected_history = tuple(histories[turn.conversation])
                if turn.conversation in blocked:
                    observation = ObservedTurn(
                        case.id, turn.id, execution_error="dependency_failed"
                    )
                else:
                    recorder = CallRecorder()
                    start = monotonic()
                    stage = "conversation_create_failed"
                    try:
                        if turn.conversation in unavailable_parents:
                            raise RegressionError("regression_conversation_unavailable")
                        stage = "provider_setup_failed"
                        rewrite, answer = providers(case, turn)
                        rag = RAGServices(
                            RecordingRewriter(rewrite, recorder), normalizer, expander, inference
                        )
                        stage = "accept_failed"
                        accepted = await repo.accept(
                            owner, parents[turn.conversation], uuid4(), turn.question
                        )
                        stage = "claim_failed"
                        job = await repo.claim(uuid4(), conversation_id=parents[turn.conversation])
                        if job is None or job.turn_id != accepted.id:
                            raise RegressionError("regression_claim_failed")
                        error = None
                        try:
                            await process_job(
                                pool, job, settings, RecordingAnswer(answer, recorder), rag=rag
                            )
                        except Exception:
                            error = "pipeline_failed"
                        stage = "observation_failed"
                        observation = await _observe(
                            pool,
                            job,
                            case.id,
                            turn,
                            recorder,
                            sections,
                            int((monotonic() - start) * 1000),
                            error,
                        )
                    except Exception:
                        observation = _failed_observation(case.id, turn, recorder, start, stage)
                    if (
                        observation.execution_error
                        or observation.result is None
                        or observation.result.kind == "error"
                    ):
                        blocked.add(turn.conversation)
                    else:
                        histories[turn.conversation].extend(
                            (
                                ContextMessage(role="user", text=turn.question),
                                ContextMessage(role="assistant", text=observation.result.text),
                            )
                        )
                verdict = judge_turn(
                    turn,
                    observation,
                    expected_history=expected_history,
                    catalog_index=catalog,
                )
                observations.append((observation, verdict))
            results.append(ScenarioResult(case.id, tuple(observations)))
    finally:
        inference.close()
    metadata: dict[str, object] = {
        "run_id": str(uuid4()),
        "started_at": started_at,
        "corpus_version": manifest.corpus_version,
        "corpus_hash": manifest.aggregate_hash,
        "ranking_version": manifest.ranking_version,
        "nlp_policy_version": normalizer.identity.policy_version,
        "rewrite_prompt_version": 2,
        "answer_prompt_version": 3,
        "configured_answer_model": settings.model,
        "configured_rewrite_model": settings.effective_rewrite_model,
        "cost": None,
    }
    return RegressionRun(
        mode="live" if mode == "live" else "offline", metadata=metadata, scenarios=tuple(results)
    )
