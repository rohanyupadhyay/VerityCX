<!-- Documents the developer command module and its operational contracts. -->

# Developer Commands

## Purpose and Structure

`scripts/` contains thin, project-root-resolving entry points for the τ³-Banking dependency:

- `setup_tau3_data.py` installs or validates the exact configured checkout.
- `inspect_tau3_banking_data.py` reports only approved aggregate metadata from an existing checkout.

Both scripts depend on `veritycx.data_sources.tau3`, Python 3.12, the fixed TOML configuration, and
Git 2.34 or newer. They expose no source, revision, path, credential, or configuration overrides.
From outside the project root, select the same locked project explicitly and use an absolute script
path: `uv run --project <absolute-project-root> --locked python <absolute-script-path>`. This keeps
the caller's working directory unchanged and requires no `PYTHONPATH` or `sys.path` modification.

## Setup and Check Modes

| Command | Successful mode | Network | Mutation |
|---|---|---|---|
| `uv run python scripts/setup_tau3_data.py` on first use | `installed` | Clone only | Owned lock/staging and final promotion |
| The same command on a valid checkout | `existing` | None | None |
| `uv run python scripts/setup_tau3_data.py --check` | `check` | None | None |

Setup validates configuration, target kind, Git prerequisites, exact origin/HEAD/tag, cleanliness,
and required data. A first install uses a cooperative lock and a unique same-filesystem staging
directory. It promotes only a completely validated checkout and cleans only state created by that
invocation. Existing targets, foreign locks, stale staging, concurrent destinations, local changes,
and neighboring cache entries are preserved for manual recovery.

## Inspection

Run `uv run python scripts/inspect_tau3_banking_data.py`. Inspection accepts no operational options.
It validates twice, buffers its result, and prints tag, commit, recursive document/task counts, and
sorted top-level database name/kind/direct-count shapes only when both observations agree. It never
creates a cache, lock, staging directory, report, or checkout.

## Output, Failure, and Testing

Success is deterministic line-oriented stdout. Expected failures produce one
`error[category]: reason=...; path="..."; recovery=...` line on stderr and exit `1`; the JSON-escaped
`path` field is omitted when no configured or current-run-owned path applies. Invalid usage is
argparse exit `2`. No expected failure emits a traceback or partial success output. Diagnostics
exclude credentials, raw Git commands/status, descendant filenames, and source-derived content.

Verify both interfaces with:

```text
uv run pytest tests/data_sources/test_tau3.py
uv run ruff check scripts
uv run mypy --strict scripts
```

## Support Database Management

`uv run python scripts/setup_support_local.py` performs the one-command Linux/WSL bootstrap for
the dedicated test database. It downloads and verifies PostgreSQL 18.6, builds it under ignored
`.cache/support/postgresql/`, initializes an owned loopback-only cluster on port `55432`, creates
separate administrator/runtime credentials and the `veritycx_support_test` database, applies all
migrations, and writes shell exports to ignored `.cache/support/local/test.env`. Re-running the
command reuses and validates its owned setup. It refuses an existing unmarked data directory and
never resets or adopts another cluster. Use `--check` for read-only layout validation.

After setup, load the generated environment only into the terminal running database-backed tests:

```text
source .cache/support/local/test.env
output=$(uv run python scripts/manage_support.py corpus prepare --mode synthetic)
hash=${output##*hash=}
uv run python scripts/manage_support.py corpus approve --hash "$hash"
uv run pytest tests -m "not live"
```

`uv run python scripts/manage_support.py db migrate` applies checksummed application migrations
and the pinned saver schema to a dedicated `veritycx_support` or `veritycx_support_test` database.
It reads only `VERITYCX_MIGRATION_DATABASE_URL`, never the runtime DSN as fallback. Native
PostgreSQL 18.6 and separate administrator/runtime roles are required; see Feature 002 quickstart.
The command never drops a database. Expected failures print a safe category and return 1;
success prints `migration_complete` and returns 0. Test via
`uv run pytest tests/support/contract/test_management.py` and the marked migration integration test.

`uv run python scripts/manage_support.py auth init-demo` provisions two synthetic identities under
ignored `.cache/support/credentials/`, prints only the generated paths and refuses overwrite.
Pass its `auth.json` path through `VERITYCX_AUTH_FILE`; keep the client token files local.

Corpus management supports fixed synthetic/official modes and explicit unchanged-hash approval:
`uv run python scripts/manage_support.py corpus prepare --mode synthetic` then
`uv run python scripts/manage_support.py corpus approve --hash HASH`. No arbitrary source flag exists.
`uv run python scripts/validate_support.py --suite offline` requires `VERITYCX_TEST_DATABASE_URL`
for the dedicated database, launches only owned API/worker processes, runs support tests plus knowledge/handoff workflows
and prints aggregate outcomes. Grounding/demo suites require explicit `--live`, credentials and
dedicated test storage. Grounding returns nonzero with human review pending; structural results
do not certify semantic correctness. The demo uses only a previously approved official corpus.
`setup_support_ci.py` separately initializes a fresh CI-owned native cluster and database roles; it
refuses use outside GitHub Actions and does not reset existing clusters.
