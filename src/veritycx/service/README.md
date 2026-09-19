<!-- Documents the service module's implemented interfaces and current limits. -->

# service

Authenticated local API, startup and validation infrastructure.

`configuration.py` loads strict nonsecret `config/support.toml` plus named environment secrets;
`runtime.py` selects a Psycopg-compatible Selector loop before any async connections.
`auth.py` provisions two 256-bit synthetic tokens into new ignored files and compares all digest rows
in constant time. `app.py` owns one bounded connection pool and sanitized errors; `routes.py` implements
create, submit, poll, delete and current-pause resume with server-derived ownership, bounded JSON and UUID idempotency keys.
`health.py` distinguishes liveness from reviewed corpus/schema, fresh worker and cleanup readiness.
`main.py` launches one loopback API without reload. Human requests persist a truthful disconnected pause; resume queues a fenced control job.

Run `uv run python scripts/manage_support.py auth init-demo`, set `VERITYCX_DATABASE_URL` and
`VERITYCX_AUTH_FILE`, then `uv run python -m veritycx.service.main`. Migration credentials never enter
runtime configuration. Provider/corpus are the only launcher overrides. No public bind is supported.
`validation.py` owns isolated API/worker subprocesses, requires a dedicated test database and retains
only aggregate evidence; `uv run python scripts/validate_support.py --suite offline` runs the support tests and actual
HTTP knowledge/handoff cases. Grounding requires `--live` and remains pending human review;
the official demo requires a previously reviewed corpus and explicit live credentials. The validation driver never kills by arbitrary PID or resets a database.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/service`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
