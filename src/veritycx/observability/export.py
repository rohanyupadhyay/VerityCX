"""Send newly constructed metadata through the documented LangSmith REST run boundary."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from pydantic import SecretStr

from veritycx.persistence.models import AuditEventRow


def metadata(event: AuditEventRow, provider: str) -> dict[str, object]:
    """Omit private associations, bodies, inherited tags and arbitrary exception objects."""
    return {
        "correlation_id": str(event.correlation_id),
        "route": event.route,
        "outcome": event.outcome,
        "source_ids": list(event.source_ids),
        "elapsed_ms": event.elapsed_ms,
        "failure_category": event.failure_category,
        "provider": provider,
        "model": event.model,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "prompt_version": "knowledge-v1",
    }


class TraceExporter:
    """Perform bounded best-effort export without SDK ambient environment enrichment."""

    def __init__(self, client: httpx.AsyncClient, key: SecretStr, project: str) -> None:
        """Receive explicit trusted transport/configuration; never inspect tracing environment."""
        self.client = client
        self.key = key
        self.project = project
        self.failures = 0

    async def send(self, payload: dict[str, object]) -> bool:
        """Send only caller-constructed metadata; isolate transport/HTTP errors locally."""
        end = datetime.now(UTC)
        elapsed = payload.get("elapsed_ms", 0)
        duration = elapsed if isinstance(elapsed, int) and elapsed >= 0 else 0
        run = {
            "id": str(uuid4()),
            "name": "veritycx-support",
            "run_type": "chain",
            "session_name": self.project,
            "inputs": {},
            "outputs": {},
            "start_time": (end - timedelta(milliseconds=duration)).isoformat(),
            "end_time": end.isoformat(),
            "extra": {"metadata": payload},
        }
        try:
            response = await self.client.post(
                "https://api.smith.langchain.com/runs",
                json=run,
                headers={"x-api-key": self.key.get_secret_value()},
                timeout=2,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            self.failures += 1
            return False
        return True
