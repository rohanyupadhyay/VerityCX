<!-- Documents the orchestration module's implemented interfaces and current limits. -->

# orchestration

Typed intent routing and fenced knowledge graph execution.

`state.py` defines the primitive graph projection. `router.py` implements versioned deterministic
English intent rules with no model calls or banking capabilities. `graph.py` checks current database
authority, routes, retrieves approved evidence, journals provider output and commits one bounded
answer through independent policy gates. Raw LangSmith tracing is disabled around graph execution.
`worker.py` claims jobs at the one-second cadence, runs at most ten concurrently and renews leases
every five seconds. `uv run python -m veritycx.orchestration.worker` runs the worker with the same
runtime configuration and corpus as the API. Interrupt/resume uses server-authorized pause IDs and operation rows. Human requests save
context before interrupting; no inbox is connected and nobody is notified.

Application rows govern ownership, counts, budgets and terminal answers. Checkpoints cannot overwrite
these values or grant authority. Losing a lease cancels local execution; stale writes fail. The
checkpoint saver guard and rollback tests must continue passing before changing graph integration.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/orchestration`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).

## Implemented Continuity

`recovery.py` reconciles terminal normal turns without model replay and blocks corrupt checkpoints for operator remediation. Worker startup purges eligible content before publishing its heartbeat and repeats maintenance hourly. Twenty actual subprocess restart/retry/concurrency cases and thirty deterministic load turns passed locally; escalation/resume and missing-interrupt repair also have native tests.
