<!-- Documents the knowledge module's implemented interfaces and current limits. -->

# knowledge

Approved document ingestion and bounded lexical retrieval.

`documents.py` parses closed id/title/content JSON from at most 1 MiB of verified bytes.
`manifest.py` prepares immutable hash inventories and activates only explicitly approved unchanged
hashes. `index.py` emits deterministic heading/paragraph sections capped at 2000 characters.
`retrieval.py` applies the reviewed log-weighted lexical overlap, stable ID ties, six-section/12000
character evidence cap and 16000-character contiguous prior context. `configuration.py` resolves
only fixed synthetic/official roots and checks official Git provenance without reading banking data.
`models.py` defines strict document, evidence and manifest contracts.

Prepare with `uv run python scripts/manage_support.py corpus prepare --mode synthetic`, then review
and run `uv run python scripts/manage_support.py corpus approve --hash HASH`. Artifacts live under
ignored `.cache/support/corpora/`. Source changes fail closed; no automatic approval, embeddings,
web fetching, task evaluation or banking-record reads. The derived index is not trusted on restore;
verified source bytes reconstruct sections. Live grounding review remains pending.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/knowledge`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
