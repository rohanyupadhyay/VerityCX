"""Record provider boundaries and replay finite authored validation outputs."""

from collections.abc import Callable, Mapping

from openai import AsyncOpenAI

from veritycx.providers.openai import OpenAIProvider
from veritycx.providers.protocol import (
    KnowledgeProvider,
    ProviderError,
    ProviderRequest,
    ProviderResult,
)
from veritycx.providers.rewrite import (
    OpenAIQueryRewriter,
    QueryRewriter,
    RewriteRequest,
    RewriteResult,
)
from veritycx.service.configuration import Settings
from veritycx.service.retrieval_cases import RegressionScenario, RegressionTurn, ReplayTurn
from veritycx.service.retrieval_checks import CallRecorder

type ProviderFactory = Callable[
    [RegressionScenario, RegressionTurn], tuple[QueryRewriter, KnowledgeProvider]
]


class RecordingRewriter:
    """Observe the real invocation without supplying gold expectations to the delegate."""

    def __init__(self, delegate: QueryRewriter, recorder: CallRecorder) -> None:
        """Retain only the explicit delegate and run-owned recorder."""
        self.delegate, self.recorder = delegate, recorder

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Preserve the exact request, result and exception behavior of one call."""
        self.recorder.rewrite_requests.append(request)
        try:
            result = await self.delegate.rewrite(request)
        except Exception:
            self.recorder.rewrite_results.append(None)
            raise
        self.recorder.rewrite_results.append(result)
        return result


class RecordingAnswer:
    """Keep answer attempts observable without changing application-owned retries."""

    def __init__(self, delegate: KnowledgeProvider, recorder: CallRecorder) -> None:
        """Retain only the explicit delegate and run-owned recorder."""
        self.delegate, self.recorder = delegate, recorder

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Capture calls at the actual provider boundary, including failed attempts."""
        self.recorder.answer_requests.append(request)
        try:
            result = await self.delegate.generate(request)
        except Exception:
            self.recorder.answer_results.append(None)
            raise
        self.recorder.answer_results.append(result)
        return result


class ReplayRewriter:
    """Return one explicitly authored interpretation, never a live-model fallback."""

    def __init__(self, replay: ReplayTurn) -> None:
        """Bind the response to a scenario and turn before invocation."""
        self.replay = replay

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Replay only the authored output; no semantic-quality claim is implied."""
        return self.replay.rewrite


class ReplayAnswer:
    """Return only authored claims or nonanswers from the separate replay file."""

    def __init__(self, replay: ReplayTurn) -> None:
        """Bind finite authored outputs without reading their expected verdicts."""
        self.replay = replay

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Keep partial-overview claim choices inside supplied evidence membership."""
        result = self.replay.answer
        if result is None:
            raise ProviderError("invalid_output")
        if self.replay.available_claims_only:
            available = {item.section_id for item in request.evidence}
            claims = tuple(claim for claim in result.claims if set(claim.evidence_ids) <= available)
            if not claims:
                raise ProviderError("invalid_output")
            return result.model_copy(update={"claims": claims})
        return result


def replay_provider_factory(replays: Mapping[tuple[str, str], ReplayTurn]) -> ProviderFactory:
    """Resolve replay records by both scenario and turn, preserving conversation independence."""

    def providers(
        case: RegressionScenario, turn: RegressionTurn
    ) -> tuple[QueryRewriter, KnowledgeProvider]:
        """Construct explicit delegates, with no access to gold outcome data."""
        replay = replays[(case.id, turn.id)]
        return ReplayRewriter(replay), ReplayAnswer(replay)

    return providers


def live_provider_factory(client: AsyncOpenAI, settings: Settings) -> ProviderFactory:
    """Bind actual provider adapters without loading any replay or expected answer."""
    rewrite = OpenAIQueryRewriter(client, settings.effective_rewrite_model)
    answer = OpenAIProvider(client, settings.model)

    def providers(
        case: RegressionScenario, turn: RegressionTurn
    ) -> tuple[QueryRewriter, KnowledgeProvider]:
        """Return shared bounded adapters; scenario gold is never included in requests."""
        return rewrite, answer

    return providers
