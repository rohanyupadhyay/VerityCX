<!-- Documents the providers module's implemented interfaces and current limits. -->

# providers

Bounded knowledge-provider implementations.

## Conversational rewriting

rewrite.py defines separate bounded search/clarify results and live/offline
QueryRewriter adapters. The live adapter uses the independently configured
rewrite model, no tools, no storage, and no SDK retries, with a ten-second cap.
rewrite_execution.py reserves one call in the separate rewrite ledger before
dispatch and reuses validated results after restart. An uncertain reserved call
is spent; a technical failure returns a retry message without raw-query fallback.
The original question, rewritten search metadata, and authoritative evidence
remain distinct in answer generation. WordNet does not make another model call.

Rewrite prompt/schema 2 adds focused/category_overview scope and distinct canonical
service-category keys. Availability hints come from the approved corpus snapshot.
Unknown keys, inconsistent scope and malformed output fail with the existing retry
message; no local classifier or live-failure substitute is introduced.
Answer prompt 3 receives scope and measured coverage as search metadata. It can
list documented products without demanding a complete catalogue, while preserving
the original question and unsupported qualifiers. Overview publication reserves
space for the fixed partial-list note within the unchanged 8000-character limit.
Focused answers and non-answer dispositions receive no note.

`protocol.py` defines closed requests/results and the `KnowledgeProvider` protocol.
`deterministic.py` implements exactly the forty authored fixture cases and abstains outside them.
`openai.py` adapts the pinned Responses SDK with structured output, no tools, store=false, 2048 output
tokens and max_retries=0. Its wire schema separates cited answers from clarification/abstention
text in a nested union. The adapter supplies model and usage metadata from configuration and the
SDK response, then constructs the existing strict internal result. `execution.py` reserves calls
in PostgreSQL, enforces the remaining deadline,
reuses journaled output and permits at most two attempts. Every failed/crashed reservation is spent.

Live selection uses `--provider openai` and requires `OPENAI_API_KEY`. Default deterministic mode
uses no paid credentials and proves only control flow. All provider content is untrusted; the
separate output policy checks selected evidence membership. Unknown usage stays null. Raw provider
errors are normalized. A bounded live request with the updated local key returned a cited synthetic
fee answer on 2026-10-28. The complete live matrix and human rubric acceptance remain pending.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/providers`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
