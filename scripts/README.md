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

### Local application setup

Run `uv run python scripts/setup_support_local.py --app` to bootstrap the interactive
application as well as the dedicated test database. It reuses the same owned cluster,
creates the separate `veritycx_support` database and limited runtime role, applies the
existing migrations, and creates or validates demo credentials under
`.cache/support/credentials/`. App runtime credentials are saved separately in
`.cache/support/local/app-credentials.json`; reruns do not rotate them. Existing app
roles/databases without saved setup credentials are refused rather than adopted.

The script fills only missing or empty `VERITYCX_DATABASE_URL`,
`VERITYCX_MIGRATION_DATABASE_URL`, and `VERITYCX_AUTH_FILE` assignments in root `.env`.
It preserves unrelated content and matching nonempty values. Malformed dotenv, duplicate
target assignments, symlink targets, literal `${...}` in generated values, and conflicting nonempty values are refused without
replacing the file. Conflicts report `local_support_app_configuration_conflict`; review
the existing values locally before clearing only settings you intend the helper to own.
Generated dotenv and credential files are private; output contains paths and statuses only.

`--app --check` validates app credential/configuration files without connecting to PostgreSQL
or generating anything. `local_support_app_setup_ready` describes configuration readiness;
the HTTP readiness endpoint checks the actual database, schema, worker, and corpus.

Setup reports `corpus=approved` or `corpus=approval_required`. It never approves documents
or calls a paid provider. When approval is required, run the existing corpus preparation
and explicit hash approval commands below. Then start the API and worker in separate
terminals using `uv run python -m veritycx.service.main` and
`uv run python -m veritycx.orchestration.worker`. Check
`curl --fail-with-body http://127.0.0.1:8000/health/ready` for readiness.

Contract coverage: `uv run pytest tests/support/contract/test_local_setup.py`. Default
test-only setup and its generated environment remain unchanged.

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

## Customer page and Chatwoot commands

`uv run python scripts/run_support.py --provider openai --build` builds the customer
page and supervises the loopback API and worker together. It requires Node.js 24 and
a valid existing server-side OpenAI key. The default provider follows `support.toml`;
live selection is explicit, and no key or Chatwoot token is bundled into frontend assets.
`--setup` invokes the existing app database bootstrap first. Without `--build`, an
existing build is reused; a missing build is created automatically. Frontend and service
diagnostics stay in private files under `.cache/support/local/`. Ctrl+C terminates only
owned child handles, while an occupied API port fails without affecting its listener.

`uv run python scripts/setup_chatwoot.py --check` inspects Docker and owned deployment
configuration without installing anything or writing secrets. Normal setup uses
`uv run python scripts/setup_chatwoot.py --allow-local-webhooks`; the explicit flag
allows local callback URLs inside this isolated Docker deployment. The helper provisions
its own Chatwoot 4.19.1, PostgreSQL and Redis storage, synthetic administrator, website
inbox, signed AgentBot and private stable credentials, then applies the integration
migration through `manage_support.py db migrate`. It never adopts foreign containers,
volumes or accounts, or installs Docker using privileged commands. See the
[local guide](../docs/chatwoot-local-setup.md) for host networking requirements and open
real-server acceptance checks.

`chatwoot_provision.rb` runs only through the pinned container's Rails runner. It checks
ownership transactionally and writes its integration result only to private setup logs.
Shared non-overwriting dotenv generation lives in
`veritycx.service.local_environment`; scripts never modify import paths.

Run `uv run pytest tests/support/contract/test_run_support.py tests/support/contract/test_customer_page.py tests/support/contract/test_chatwoot_setup.py`
for the command and public-page contracts. The signed adapter has additional unit and
dedicated-database integration tests documented in its module README.

## Environment Contract

`manage_support.py` and `validate_support.py` load the optional root `.env` before reading any
project-owned setting; explicit process values retain precedence. Their existing validation and exit
categories remain authoritative when a required value is absent. Explicit environment mappings used
inside support libraries and subprocess tests do not trigger ambient loading.

`uv run python scripts/check_environment_contract.py` statically derives literal project-owned
reads from maintained Python sources, strictly parses `.env.example`, and requires exact name
equality. Missing, extra, duplicate, malformed, wrong-case, unsafe-placeholder, and dynamic-read
findings exit `1` with sorted name-only output; success exits `0` with
`environment_contract_ok`. The checker never opens `.env`. Correct the named source/template drift,
and use only empty or obvious synthetic placeholders in the tracked example.
