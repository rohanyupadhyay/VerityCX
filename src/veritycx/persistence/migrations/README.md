<!-- Documents versioned application schema migrations and administrative ownership. -->

# Support migrations

`001_support.sql` defines durable entities, ownership relationships, one active job/pause,
operation uniqueness, bounds and worker heartbeats. `migrate.py` applies it transactionally under an
administrative connection and a session advisory lock. The checksum ledger is in `support_meta`.
Checkpoint setup uses the pinned library's administrative migrations in `support_checkpoints`;
its concurrent-index steps run outside the application migration transaction and are restartable.

Runtime has schema usage and data access, never DDL or ledger writes. Never edit an applied SQL
file: add a reviewed numbered migration and extend the runner instead. Current runner supports
only version 001 and fails closed on drift. Invoke via the upcoming root management command.
Run `uv run pytest tests/support/integration/test_migrations.py` with explicit dedicated test
runtime/admin DSNs. No database is dropped or reset by migration or tests.
