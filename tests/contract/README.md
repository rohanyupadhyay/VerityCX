<!-- Documents tests for the tracked environment-name contract. -->

# Environment contract tests

`test_environment_contract.py` validates source-derived ownership, strict `.env.example` parsing,
exact name equality, safe placeholders, deterministic name-only diagnostics, and the live repository
inventory. Run it from the Git root with `uv run pytest tests/contract/test_environment_contract.py`.

Fixtures use temporary source and template files. The checker must never open a real `.env`, inherit
configuration values into diagnostics, or print seeded secret canaries. Findings use only categories,
names, and safe source locations.
