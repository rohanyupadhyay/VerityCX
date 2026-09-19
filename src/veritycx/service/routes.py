"""Implement authorized create/submit/poll boundaries with strict bounded JSON and safe errors."""

from collections.abc import Callable
from uuid import UUID

from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response

from veritycx.conversations.models import (
    CreateInput,
    EscalationView,
    ResumeFailure,
    ResumeInput,
    ResumeOperationView,
    TurnInput,
    canonical_uuid,
    parse_json,
)
from veritycx.knowledge.configuration import active_corpus
from veritycx.persistence.database import DatabasePool, transaction
from veritycx.persistence.escalations import resume
from veritycx.persistence.models import EscalationRow, TurnRow, WorkJob
from veritycx.persistence.repository import Repository, live_parent
from veritycx.service.auth import DemoPrincipal, authenticate
from veritycx.service.configuration import RuntimeConfiguration


class ServiceError(ValueError):
    """Carry a reviewed HTTP category without reflecting client values."""

    def __init__(self, code: str, status: int) -> None:
        """Set the safe category and HTTP status used by the error handler."""
        self.code = code
        self.status = status
        super().__init__(code)


async def body_model[T: BaseModel](request: Request, model: type[T]) -> T:
    """Bound streamed input before strict UTF-8/duplicate-key/model validation."""
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 65536:
            raise ServiceError("payload_too_large", 413)
        body.extend(chunk)
    return model.model_validate(parse_json(bytes(body)))


def request_key(request: Request) -> UUID:
    """Require a canonical UUID idempotency key on each mutation."""
    return UUID(canonical_uuid(request.headers.get("Idempotency-Key", "")))


def register_routes(
    app: FastAPI,
    configuration: RuntimeConfiguration,
    principals: tuple[DemoPrincipal, ...],
    pool_getter: Callable[[], DatabasePool],
) -> None:
    """Bind routes to trusted configuration/principals without exposing client-owned state."""

    @app.post("/conversations")
    async def create(request: Request) -> JSONResponse:
        """Authorize before accepting a new durable conversation."""
        owner = authenticate(request.headers.get("Authorization"), principals)
        await body_model(request, CreateInput)
        key = request_key(request)
        manifest, _ = active_corpus(configuration.settings.corpus_mode)
        parent = await Repository(pool_getter()).create(owner, key, manifest.corpus_version)
        return JSONResponse(
            {
                "schema_version": 1,
                "conversation_id": str(parent.id),
                "revision": parent.revision,
                "status": parent.status,
                "expires_at": parent.expires_at.isoformat(),
            },
            status_code=201,
        )

    @app.post("/conversations/{conversation_id}/turns")
    async def submit(conversation_id: str, request: Request) -> JSONResponse:
        """Acknowledge only after message/job/audit/key commit succeeds."""
        owner = authenticate(request.headers.get("Authorization"), principals)
        target = UUID(canonical_uuid(conversation_id))
        value = await body_model(request, TurnInput)
        key = request_key(request)
        turn = await Repository(pool_getter()).accept(owner, target, key, value.message)
        return JSONResponse(
            {
                "schema_version": 1,
                "operation_id": str(key),
                "conversation_id": str(target),
                "turn_id": str(turn.id),
                "status": turn.status,
                "poll_url": f"/conversations/{target}",
            },
            status_code=202,
        )

    @app.get("/conversations/{conversation_id}")
    async def read(conversation_id: str, request: Request) -> JSONResponse:
        """Project application rows under one owner/live-parent lock, never checkpoint internals."""
        owner = authenticate(request.headers.get("Authorization"), principals)
        target = UUID(canonical_uuid(conversation_id))
        async with transaction(pool_getter()) as conn:
            parent = await live_parent(conn, target, owner)
            cursor = await conn.execute(
                "SELECT * FROM support_app.turns WHERE conversation_id=%s ORDER BY sequence",
                (target,),
            )
            turns = [TurnRow.model_validate(row) for row in await cursor.fetchall()]
            cursor = await conn.execute(
                "SELECT * FROM support_app.escalations WHERE conversation_id=%s AND "
                "status='pending'",
                (target,),
            )
            pause_row = await cursor.fetchone()
            escalation = None
            if pause_row:
                pause = EscalationRow.model_validate(pause_row)
                escalation = EscalationView(
                    pause_id=str(pause.pause_id), reason=pause.reason, summary=pause.summary
                )
            cursor = await conn.execute(
                "SELECT j.*,o.request_key FROM support_app.jobs j JOIN "
                "support_app.operations o ON o.resource_id=j.id WHERE "
                "j.conversation_id=%s AND o.kind='resume' ORDER BY j.created_at DESC LIMIT 1",
                (target,),
            )
            resume_row = await cursor.fetchone()
            latest = None
            if resume_row:
                operation_id = resume_row.pop("request_key")
                resume_job = WorkJob.model_validate(resume_row)
                latest = ResumeOperationView(
                    operation_id=str(operation_id),
                    status=resume_job.status,
                    failure=resume_failure(resume_job),
                )
            return JSONResponse(
                {
                    "schema_version": 1,
                    "conversation_id": str(target),
                    "revision": parent.revision,
                    "status": parent.status,
                    "expires_at": parent.expires_at.isoformat(),
                    "turns": [
                        {
                            "turn_id": str(turn.id),
                            "sequence": turn.sequence,
                            "message": turn.text,
                            "status": turn.status,
                            "result": turn.result.model_dump(mode="json") if turn.result else None,
                        }
                        for turn in turns
                    ],
                    "escalation": escalation.model_dump(mode="json") if escalation else None,
                    "latest_resume_operation": latest.model_dump(mode="json") if latest else None,
                }
            )

    @app.post("/conversations/{conversation_id}/resume")
    async def continue_automation(conversation_id: str, request: Request) -> JSONResponse:
        """Consume explicit consent into a durable control operation before acknowledgment."""
        owner = authenticate(request.headers.get("Authorization"), principals)
        target = UUID(canonical_uuid(conversation_id))
        value = await body_model(request, ResumeInput)
        key = request_key(request)
        job = await resume(pool_getter(), owner, target, key, value)
        failure = resume_failure(job)
        return JSONResponse(
            {
                "schema_version": 1,
                "operation_id": str(key),
                "conversation_id": str(target),
                "turn_id": None,
                "status": job.status,
                "poll_url": f"/conversations/{target}",
                "failure": failure.model_dump(mode="json") if failure else None,
            },
            status_code=202,
        )

    @app.delete("/conversations/{conversation_id}")
    async def delete(conversation_id: str, request: Request) -> Response:
        """Revoke access before acknowledging deletion, retaining only safe identical retries."""
        owner = authenticate(request.headers.get("Authorization"), principals)
        target = UUID(canonical_uuid(conversation_id))
        async for chunk in request.stream():
            if chunk:
                raise ServiceError("invalid_input", 422)
        await Repository(pool_getter()).delete(owner, target, request_key(request))
        return Response(status_code=202)


def resume_failure(job: WorkJob) -> ResumeFailure | None:
    """Project only validated, sanitized failure fields from a durable control job."""
    if job.failure_code is None or job.recovery is None:
        return None
    return ResumeFailure(code=job.failure_code, recovery=job.recovery)
