<!-- Documents the observability module's implemented interfaces and current limits. -->

# observability

Atomic local audit and separately gated sanitized export.

`audit.py` commits a terminal customer result and its audit outcome in one fenced transaction.
Acceptance audit is created by the repository with correlation, pending route and accepted outcome;
completion fills source IDs, elapsed time, failure category and optional model/usage metadata.
No customer content is logged by this module. Local audit is conversation-scoped and will be purged
with retention. `export.py` implements opt-in metadata-only LangSmith REST export; raw graph auto-tracing
is disabled even when inherited environment settings enable it. Inputs and outputs are empty.
The exporter uses the [documented run API](https://docs.langchain.com/langsmith/trace-with-api)
to avoid SDK enrichment from ambient metadata. Export failure must never change a committed response. No external account is needed
for the current offline tests.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/observability`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
