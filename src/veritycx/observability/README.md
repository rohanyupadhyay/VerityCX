<!-- Documents the observability module's implemented interfaces and current limits. -->

# observability

Atomic local audit and separately gated sanitized export.

Category retrieval adds local requested-category and document-coverage diagnostics.
Coverage counts source documents, not an exhaustive product catalogue. Answer audit
records persist the answer prompt version for newly committed results. Exports use
that event's knowledge-vN value, or unknown for historical/unverifiable provenance;
restarting a newer worker does not relabel an older event.

Rewriting keeps separate model, prompt version, observed token counts, start/end
timestamps, and failure categories in the turn-owned query_rewrites row. Retrieval
also records selected section IDs, selection mode and expansion count there, even
when answering abstains. Rewritten queries remain private conversation content:
they are never added to ordinary logs or exported tracing. Existing answer audit
usage is not relabeled as combined rewrite/answer usage.

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
