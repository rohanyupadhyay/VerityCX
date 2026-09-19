"""Provide finite authored responses, explicitly distinct from live grounding evidence."""

from typing import Literal

from pydantic import Field

from veritycx.conversations.models import ClosedModel, VersionedModel, parse_json
from veritycx.providers.protocol import Claim, ProviderRequest, ProviderResult
from veritycx.service.configuration import PROJECT_ROOT


class FixtureCase(ClosedModel):
    """Freeze expected fixture behavior without importing official benchmark tasks."""

    id: str
    question: str
    disposition: Literal["answer", "clarify", "abstain"]
    required_facts: list[str]
    source_ids: list[str]


class FixtureSet(VersionedModel):
    """Validate the complete finite synthetic scenario inventory."""

    provenance: str
    cases: list[FixtureCase] = Field(min_length=40, max_length=40)


def fixture_cases() -> tuple[FixtureCase, ...]:
    """Load only the fixed project-authored question file using strict decoding."""
    path = PROJECT_ROOT / "tests" / "support" / "fixtures" / "grounding.json"
    return tuple(FixtureSet.model_validate(parse_json(path.read_bytes())).cases)


class DeterministicProvider:
    """Return finite test responses with no network, tools or runtime fault switches."""

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Resolve one exact fixture question or abstain outside the authored inventory."""
        case = next((case for case in fixture_cases() if case.question == request.question), None)
        if case is not None and case.disposition == "clarify":
            return ProviderResult(
                disposition="clarify",
                text="The sources conflict. Which policy version applies?",
                model="deterministic-fixture-v1",
            )
        available = {section.section_id for section in request.evidence}
        if case is None or case.disposition == "abstain" or not set(case.source_ids) <= available:
            return ProviderResult(
                disposition="abstain",
                text="The approved sources do not support an answer.",
                model="deterministic-fixture-v1",
            )
        return ProviderResult(
            disposition="answer",
            claims=tuple(
                Claim(text=fact, evidence_ids=tuple(case.source_ids))
                for fact in case.required_facts
            ),
            model="deterministic-fixture-v1",
        )
