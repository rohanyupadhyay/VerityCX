<!-- Documents the providers module's implemented interfaces and current limits. -->

# providers

Bounded knowledge-provider implementations.

`protocol.py` defines closed requests/results and the `KnowledgeProvider` protocol.
`deterministic.py` implements exactly the forty authored fixture cases and abstains outside them.
`openai.py` adapts the pinned Responses SDK with structured output, no tools, store=false, 2048 output
tokens and max_retries=0. `execution.py` reserves calls in PostgreSQL, enforces the remaining deadline,
reuses journaled output and permits at most two attempts. Every failed/crashed reservation is spent.

Live selection uses `--provider openai` and requires `OPENAI_API_KEY`. Default deterministic mode
uses no paid credentials and proves only control flow. All provider content is untrusted; the
separate output policy checks selected evidence membership. Unknown usage stays null. Raw provider
errors are normalized. Concrete live network execution and human rubric acceptance remain pending.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/providers`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
