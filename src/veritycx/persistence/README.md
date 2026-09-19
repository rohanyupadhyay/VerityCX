<!-- Documents the persistence responsibility boundary and its planned implementation. -->

# persistence

Durable application records, fencing, guarded checkpoints, escalation control and retention.
Implemented interfaces are listed below.

Dependencies and boundaries: native PostgreSQL 18.6, Psycopg and the pinned checkpoint saver. Configuration comes from root
`config/support.toml` and the documented environment inputs, never customer content.
See the [configuration contract](../../../../specs/002-durable-knowledge-support/contracts/configuration.md)
and [design](../../../../specs/002-durable-knowledge-support/plan.md) for the interface contracts.

From the repository root, install with `uv sync --locked --link-mode=copy` and check
with `uv run ruff check src/veritycx/persistence` and `uv run mypy`.
Feature tests live in `tests/support/`; database cases require dedicated credentials.
Missing configuration, invalid external values and unavailable storage fail safely.

## Implemented Typed Contracts

`models.py` implements strict driver-row models for conversations, turns, jobs, operations,
attempts, escalations, audit and heartbeat. SQL operations use explicit transactions and parent-before-job locks.

## Implemented Migration and Connections

`migrate.migrate(admin_dsn, runtime_role)` owns version/checksum validation, application SQL and
administrative saver setup. `verify_schema` performs read-only readiness checks. The runtime role
has DML but no schema creation or migration-ledger mutation rights. Migration SQL is versioned in
`migrations/`; never edit an applied file. Existing databases are preserved.

`database.database_pool` creates a pool capped at 20 connections with autocommit outside explicit
transactions, fixed search path and validated schema. `database.transaction` borrows one connection
for an atomic unit and rolls back errors. Use `service.runtime.run_async` before opening connections.
Migration and runtime DSNs remain separate and must not be logged. Real migration/privilege tests
run with `uv run pytest tests/support/integration/test_migrations.py` and dedicated test credentials.

## Acceptance and Guarded Checkpoints

`Repository` provides owner-scoped create/read/accept, canonical request digests, atomic audit/job
acceptance, fenced claims, renewals and worker heartbeat. `worker_guard` locks parent before job and
rejects deleted/expired parents, obsolete tokens, expired leases and old fences. Claims preserve the
first processing deadline. New work conflicts while an active job remains.

`GuardedSaver` wraps one borrowed connection. Each async checkpoint/pending write holds the same
parent/fence transaction as its mutation; checkpoint pointer publication commits atomically.
A per-saver lock prevents concurrent coroutines from interleaving transactions on that connection.
Restore uses the approved pointer and validates conversation/job/corpus binding and restricted types.
Workers cannot delete threads; `maintenance.py` owns maintenance authorization.

Run `uv run pytest tests/support` with dedicated database credentials for native rollback, stale-worker,
missing/expired/deleted parent and concurrency tests. Additional integration and subprocess tests exercise graph recovery,
provider budgets, retention and end-to-end acceptance. Hosted/live release acceptance is separate.

## Implemented Continuity

`maintenance.purge_expired` uses a separate deletion-only guard for deleted/expired parents. It invalidates fences and atomically deletes saver/application children before the parent. Runtime DELETE blocks access immediately; retained identical owner retries return acknowledgment. Corrupt checkpoint jobs retain operator-required state and prevent new work from bypassing it.
