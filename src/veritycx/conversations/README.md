<!-- Documents typed conversation contracts and truthful pause lifecycle behavior. -->

# conversations

`models.py` validates closed create, turn and resume contracts, strict JSON, bounded
results and public polling projections. `commands.py` holds immutable owner and
worker authority. `lifecycle.py` builds bounded factual escalation context and the
fixed acknowledgment that nobody has been notified.

A human request saves a pending escalation before the graph interrupt. Later messages
are retained as context and receive that same acknowledgment without invoking a
provider. Owner-authorized resume consumes the current pause and revision into a
durable control job. The conversation remains paused until graph continuation
completes. Identical retries return the original operation. Recoverable terminal
control failure issues a fresh pause; incompatible saved state requires operator
remediation. Neither path claims delivery to a human inbox.

Configuration comes from `config/support.toml`, never customer text. Persistence and
HTTP packages enforce ownership and idempotency; these models grant no authority.
Install from the repository root with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/conversations`, `uv run mypy` and
`uv run pytest tests/support/unit/test_models.py`. Native database tests require the
separate test credentials described in the [quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
