"""Check thirty authored attacks against actual authority, source and output boundaries."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from veritycx.conversations.models import ClosedModel, ResumeInput, parse_json
from veritycx.knowledge.configuration import active_corpus
from veritycx.orchestration.worker import process_job
from veritycx.persistence.database import database_pool
from veritycx.persistence.escalations import resume
from veritycx.persistence.repository import Repository, RepositoryError
from veritycx.policy.sources import SourceError, verified_bytes
from veritycx.providers.deterministic import DeterministicProvider
from veritycx.providers.protocol import ProviderRequest, ProviderResult
from veritycx.service.configuration import Settings
from veritycx.service.runtime import run_async


class Attack(ClosedModel):
    """Parse one closed authored attack without executable fixture instructions."""

    id: str
    category: str
    payload: str


class Inventory(ClosedModel):
    """Require the versioned security inventory shape."""

    schema_version: int
    provenance: str
    cases: list[Attack]


CASES = Inventory.model_validate(
    parse_json(Path("tests/support/fixtures/security.json").read_bytes())
).cases


@pytest.mark.support_db
@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_security_effects(case: Attack, test_database_url: str, tmp_path: Path) -> None:
    """Assert denied effects and unchanged authoritative ownership across each attack."""

    async def exercise() -> None:
        """Use native storage with isolated owners and no external provider access."""
        manifest, sections = active_corpus("synthetic")
        async with database_pool(test_database_url) as pool:
            repo = Repository(pool)
            owner, stranger = uuid4(), uuid4()
            parent = await repo.create(owner, uuid4(), manifest.corpus_version)
            consent = ResumeInput(
                pause_id=str(uuid4()), expected_revision=parent.revision, continue_automation=True
            )
            if case.category == "customer_injection":
                await repo.accept(owner, parent.id, uuid4(), case.payload)
                job = await repo.claim(uuid4(), conversation_id=parent.id)
                assert job is not None
                await process_job(pool, job, Settings(), DeterministicProvider())
                async with pool.connection() as conn:
                    cursor = await conn.execute(
                        "SELECT result->>'kind' AS kind FROM support_app.turns WHERE id=%s",
                        (job.turn_id,),
                    )
                    row = await cursor.fetchone()
                    assert row and row["kind"] in {"clarify", "unavailable", "abstain"}
            elif case.category == "document_injection":
                evidence = sections[0].model_copy(update={"content": case.payload})
                request = ProviderRequest(
                    correlation_id=str(uuid4()),
                    question="Explain this untrusted policy content",
                    evidence=(evidence,),
                    remaining_seconds=60.0,
                )
                result = await DeterministicProvider().generate(request)
                assert result.disposition == "abstain"
                assert (
                    "owner_id" not in request.model_dump() and "tools" not in request.model_dump()
                )
            elif case.category == "cross_owner":
                with pytest.raises(RepositoryError, match="not_found"):
                    if case.payload == "read":
                        await repo.get(stranger, parent.id)
                    elif case.payload == "delete":
                        await repo.delete(stranger, parent.id, uuid4())
                    elif case.payload == "resume":
                        await resume(pool, stranger, parent.id, uuid4(), consent)
                    else:
                        await repo.accept(stranger, parent.id, uuid4(), "foreign message")
            elif case.category == "forbidden_sources":
                (tmp_path / "db.json").write_text("PRIVATE_FILE_CANARY")
                with pytest.raises(SourceError):
                    verified_bytes(tmp_path, case.payload)
            elif case.category == "resume_tampering":
                payload = consent.model_dump()
                payload[case.payload] = (
                    False if case.payload == "continue_automation" else "attacker"
                )
                with pytest.raises(ValidationError):
                    ResumeInput.model_validate(payload)
            elif case.category == "malformed_provider":
                output: dict[str, object] = {
                    "disposition": "abstain",
                    "text": "No evidence",
                    "model": "fixture",
                }
                output[case.payload] = "attacker"
                with pytest.raises(ValidationError):
                    ProviderResult.model_validate(output)
            else:
                pytest.fail("unknown security category")
            current = await repo.get(owner, parent.id)
            assert current.owner_id == owner and current.status == "active"
            assert current.customer_count == (1 if case.category == "customer_injection" else 0)

    run_async(exercise())
