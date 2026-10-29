<!-- Documents http and management interface contracts. -->

# Support contract

HTTP and management interface contracts. The current files implement the cases and fixtures described below.
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

`test_auth.py`, `test_conversation_api.py`, `test_delete_api.py`, `test_error_privacy.py`, `test_health.py`, `test_management.py`, `test_providers.py`, `test_resume_api.py`, `test_validation_cli.py`.

`test_providers.py` exercises real SDK parsing through an offline transport for cited
answers, clarifications and abstentions, including SDK-supplied usage and configured
model identity. It also checks citation membership, malformed output and disabled retries.

`test_configuration_loading.py` requires API and worker startup to load the root dotenv before
configuration. `test_environment_commands.py` applies the same ordering contract to management and
validation commands. These tests inspect process boundaries only; explicit mapping APIs remain
ambient-environment independent.

`test_local_setup.py` covers default PostgreSQL setup guards, read-only app checks,
separate app connection identities, dotenv preservation/conflicts, and stable private
authentication. Missing-configuration subprocess tests explicitly mask local dotenv
values, so configuring the application does not change their expectations.

`test_customer_page.py` verifies public frontend delivery, unavailable builds, asset
containment and the disabled widget contract. `test_chatwoot_runtime_configuration.py`
checks optional channel configuration and pool requirements. `test_chatwoot_setup.py`
checks private owned Docker provisioning without requiring a real Docker daemon;
`test_run_support.py` checks launcher discovery, listener preservation and owned cleanup.
