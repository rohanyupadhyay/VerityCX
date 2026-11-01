"""Pin concrete edge cases identified by the independent whole-branch review."""

import sys
from pathlib import Path

import pytest

from veritycx.knowledge.index import sections
from veritycx.knowledge.models import KnowledgeDocument
from veritycx.knowledge.nlp import TextNormalizer
from veritycx.knowledge.retrieval import select_evidence
from veritycx.knowledge.synonyms import WordNetExpander


@pytest.mark.parametrize(
    "question",
    [
        "Which cards aren't eligible?",
        "Which cards aren\u2019t eligible?",
    ],
)
def test_contracted_negation_is_preserved_without_parser(question: str) -> None:
    """The selected lightweight pipeline must retain aren't as a negative constraint."""
    tokens = TextNormalizer().analyze(question)
    assert any(token.constraint and token.lemma == "not" for token in tokens)


@pytest.mark.parametrize("name", ["May", "US"])
def test_stopword_shaped_product_name_is_preserved(name: str) -> None:
    """A recognized proper name must not disappear merely because it is also a stopword."""
    tokens = TextNormalizer().analyze(f"What is the fee for the {name} card?")
    assert any(token.surface == name and token.protected for token in tokens)


@pytest.mark.parametrize(
    "original,rewritten",
    [
        ("Tell me about the Cedar card.", "Cedar"),
        ("Cedar", "Tell me about the Cedar card."),
    ],
)
def test_protection_applies_to_all_occurrences_of_merged_query_concept(
    original: str, rewritten: str
) -> None:
    """A context-dependent POS change cannot expand a previously protected product."""
    normalizer = TextNormalizer()
    evidence = sections(
        KnowledgeDocument(id="wood", title="Wood policy", content="Cedarwood is available."),
        "fixture-v2",
    )
    result = select_evidence(
        original,
        rewritten,
        evidence,
        normalizer=normalizer,
        expander=WordNetExpander(normalizer),
    )
    assert result.sections == () and result.expanded_term_count == 0


def test_management_sanitizes_missing_language_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Corpus setup must report a fixed category rather than an exception traceback."""
    from scripts import manage_support

    from veritycx.knowledge.resources import ResourceError

    def unavailable(*args: object, **kwargs: object) -> None:
        """Model an unavailable installed resource without touching actual assets."""
        raise ResourceError("nlp_resources_unavailable")

    monkeypatch.setattr(manage_support, "load_project_environment", lambda: None)
    monkeypatch.setattr(manage_support, "source_mode", lambda mode: (tmp_path, tmp_path, "fixture"))
    monkeypatch.setattr(manage_support, "prepare", unavailable)
    monkeypatch.setattr(
        sys, "argv", ["manage_support.py", "corpus", "prepare", "--mode", "synthetic"]
    )
    assert manage_support.main() == 1
    assert capsys.readouterr().out == "corpus_unavailable\n"


def test_management_approves_in_selected_test_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A prepare/approve cycle must use the same fixed test namespace."""
    from scripts import manage_support

    from veritycx.knowledge import configuration
    from veritycx.knowledge.manifest import read_active

    root = tmp_path / "tests" / "support" / "fixtures" / "documents"
    root.mkdir(parents=True)
    (root / "policy.json").write_text(
        '{"id":"fixture","title":"Card fee","content":"A synthetic fee policy."}'
    )
    monkeypatch.setattr(configuration, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(manage_support, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(manage_support, "load_project_environment", lambda: None)
    monkeypatch.setenv(
        "VERITYCX_DATABASE_URL", "host=127.0.0.1 dbname=veritycx_support_test user=fixture"
    )
    monkeypatch.setattr(
        sys, "argv", ["manage_support.py", "corpus", "prepare", "--mode", "synthetic"]
    )
    assert manage_support.main() == 0
    digest = capsys.readouterr().out.strip().split("hash=")[-1]
    monkeypatch.setattr(sys, "argv", ["manage_support.py", "corpus", "approve", "--hash", digest])
    assert manage_support.main() == 0
    _, cache, _ = configuration.source_mode("synthetic")
    assert cache.name == "test-synthetic"
    assert read_active(root, cache).aggregate_hash == digest
    assert not (tmp_path / ".cache/support/corpora/synthetic/active").exists()


def test_cancelled_nlp_counts_against_capacity_until_thread_finishes() -> None:
    """Timed-out background work cannot free advertised inference capacity prematurely."""
    import asyncio
    from threading import Event
    from typing import cast
    from uuid import uuid4

    from veritycx.orchestration.inference import InferenceCapacity
    from veritycx.orchestration.worker import publish_capacity
    from veritycx.persistence.repository import Repository
    from veritycx.service.runtime import run_async

    started, released = Event(), Event()
    events: list[str] = []

    class HeartbeatRepository:
        """Observe advertised readiness without touching another worker's database row."""

        async def heartbeat(self, worker: object) -> None:
            """Record an available worker."""
            events.append("ready")

        async def withdraw_heartbeat(self, worker: object) -> None:
            """Record a capacity-exhausted worker."""
            events.append("unavailable")

    def blocked() -> None:
        """Represent blocking model work that coroutine cancellation cannot terminate."""
        started.set()
        assert released.wait(4)

    async def exercise() -> None:
        """Cancel the waiter, check readiness, then release the actual thread."""
        capacity = InferenceCapacity(1)
        repository = cast(Repository, HeartbeatRepository())
        worker = uuid4()
        try:
            task = asyncio.create_task(capacity.run(blocked))
            while not started.is_set():
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert capacity.available_slots == 0
            assert not await publish_capacity(repository, worker, capacity, heartbeat_due=True)
            assert events == ["unavailable"]
            released.set()
            for _ in range(100):
                if capacity.available_slots == 1:
                    break
                await asyncio.sleep(0.01)
            assert capacity.available_slots == 1
            assert await publish_capacity(repository, worker, capacity, heartbeat_due=True)
            assert events == ["unavailable", "ready"]
        finally:
            released.set()
            capacity.close()

    run_async(exercise())


def test_validation_owner_scope_is_rejected_for_application_database() -> None:
    """Load-test isolation must never become an accidentally scoped application worker."""
    from uuid import uuid4

    from veritycx.orchestration.worker import validate_worker_scope
    from veritycx.service.configuration import ConfigurationError

    with pytest.raises(ConfigurationError, match="validation_scope_requires_test_database"):
        validate_worker_scope("host=127.0.0.1 dbname=veritycx_support user=fixture", uuid4())
    validate_worker_scope("host=127.0.0.1 dbname=veritycx_support_test user=fixture", uuid4())
