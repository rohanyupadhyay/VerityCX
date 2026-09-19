<!-- Documents the policy module's implemented interfaces and current limits. -->

# policy

Independent authorization, source containment and output publication rules.

`authorization.py` compares server-derived owners with validated conversation records.
`sources.py` checks lexical containment, every directory/file component, links/reparse points,
regular-file type, size and identity before/after reading. Document bytes remain untrusted.
`outputs.py` requires each answer citation to belong to the exact selected evidence, renders source
attribution server-side and bounds publication text. Schema/citation validity is not a claim of
semantic grounding quality. No policy function exposes operational banking tools or reads bank data.
Errors carry safe categories rather than source text or credentials. These controls supplement
repository fences and provider contracts; prompts do not grant authorization.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/policy`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
