<!-- Documents authored synthetic documents and expected outcomes. -->

# Support fixtures

Authored synthetic documents and expected outcomes. The current files implement the cases and fixtures described below.
Only project-authored synthetic data belongs here. No upstream documents, evaluation answers,
credentials or generated evidence may be committed.

Run from the repository root with `uv run pytest tests/support -m "not support_db and not live"`
for database-free tests, or `uv run pytest tests/support -m "not live"` for full offline validation.
The latter requires native PostgreSQL 18.6 and `VERITYCX_TEST_DATABASE_URL` naming the dedicated
`veritycx_support_test` database; missing prerequisites fail instead of skipping.
Live tests are excluded by default and require separate explicit authorization.

Shared interfaces live in `tests/support/conftest.py`: synthetic identity/document factories,
a dedicated-database fixture and process ownership guards. Test teardown may dispose only records
or subprocess handles created by that test; it must never reset unrelated databases or kill by PID.

## Current files

`grounding.json`, `security.json`.
