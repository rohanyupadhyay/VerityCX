<!-- Documents shared synthetic fixtures and guarded test resources. -->

# Support tests

Shared synthetic fixtures and guarded test resources. Cases cover strict models, authentication, migrations, guarded checkpoints, recovery, retention,
escalation/resume, trace privacy and thirty authored adversarial inputs. Deterministic document
injection tests establish bounded adapter/control behavior, not live-model injection resistance.
Only project-authored synthetic data belongs here. No upstream documents, evaluation answers,
credentials or generated evidence may be committed.

Run from the repository root with `uv run pytest tests/support -m "not support_db and not live"`
for database-free tests, or `uv run pytest tests/support -m "not live"` for full offline validation.
The latter requires native PostgreSQL 18.6 and `VERITYCX_TEST_DATABASE_URL` naming the dedicated
`veritycx_support_test` database; migration tests also require `VERITYCX_TEST_MIGRATION_DATABASE_URL`. Missing prerequisites fail instead of skipping.
Live tests are excluded by default and require separate explicit authorization.

Shared interfaces live in `tests/support/conftest.py`: synthetic identity/document factories,
a dedicated-database fixture and process ownership guards. Test teardown may dispose only records
or subprocess handles created by that test; it must never reset unrelated databases or kill by PID.

Run database suites sequentially against their dedicated database. A second worker can legitimately
claim another test's accepted jobs and invalidate a fault-hook experiment. Hosted and live acceptance
remain separate from local passing tests.

## Current files

`conftest.py`, `harness.py`.
