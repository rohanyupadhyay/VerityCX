<!-- Documents the service module's implemented interfaces and current limits. -->

# service

Authenticated local API, startup and validation infrastructure.

The API also serves the built customer page at `/` and `/chat`, with public assets
under `/assets/`. `frontend.py` restricts delivery to the root `dist/chat` build and
applies browser security headers; project files and credentials are never mounted.
Build with `npm run build` from the repository root, or use
`uv run python scripts/run_support.py --provider openai --build` to build and supervise
the API/worker together. A missing build returns an explicit unavailable response while
backend liveness remains usable.

Optional typed Chatwoot configuration exposes only the public widget origin/token through
`GET /chat/config`; signed webhook intake and durable delivery belong to the `handoff`
package. API and AgentBot tokens and the OpenAI key remain server-side. The worker runs
the bridge only when fully configured; it requires a pool of at least two connections.
The standalone conversation API retains its original owner authorization and disconnected
escalation semantics. Core migrations remain immutable; Chatwoot uses an independent ledger.

`local_environment.py` supplies shared private, atomic dotenv generation for setup
commands. It preserves unrelated/matching values and refuses conflicts, malformed
assignments, symlinks and generated values containing interpolation syntax. Ordinary
runtime configuration still uses the existing non-overwriting root environment loader.

`configuration.py` loads strict nonsecret `config/support.toml` plus named environment secrets;
`runtime.py` selects a Psycopg-compatible Selector loop before any async connections.
`auth.py` provisions two 256-bit synthetic tokens into new ignored files and compares all digest rows
in constant time. `app.py` owns one bounded connection pool and sanitized errors; `routes.py` implements
create, submit, poll, delete and current-pause resume with server-derived ownership, bounded JSON and UUID idempotency keys.
`health.py` distinguishes liveness from reviewed corpus/schema, fresh worker and cleanup readiness.
`main.py` launches one loopback API without reload. Human requests persist a truthful disconnected pause; resume queues a fenced control job.

At process startup, `main.py` calls `load_project_environment()` before reading configuration. The
root `.env` is optional and never overrides an explicit process value. `load_configuration()` keeps
its explicit mapping interface and does not read ambient dotenv state itself; malformed dotenv files
fail with the secret-safe `invalid_environment_file` category before configuration validation.

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
