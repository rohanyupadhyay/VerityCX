<!-- Documents the VerityCX project purpose, setup workflow, and quality gates. -->

# VerityCX

VerityCX is a Python 3.12 project for reproducible customer-experience research tooling. Feature
001 provides developer-only acquisition and validation of the external τ³-Banking dataset. It
does not import that data into the application or build retrieval, agent, API, container, or
evaluation behavior.

## Repository Root

The directory containing `.git` is the project root. Run **all commands below from this directory**;
do not enter a nested project directory. Python metadata, scripts, tests, CI, and GitHub Spec Kit
share this root.

The broader [platform vision](docs/project-vision.md) describes future work, not implemented features.
The [roadmap](docs/platform-roadmap.md), [design](docs/platform-design.md), and
[threat model](docs/threat-model.md) describe the proposed platform. Feature 002 implements
[durable knowledge support](specs/002-durable-knowledge-support/quickstart.md): authenticated FastAPI,
approved-document retrieval, LangGraph routing, PostgreSQL recovery, truthful escalation/resume
and opt-in metadata tracing. Local deterministic checks are recorded in its quickstart; hosted
and human-reviewed live acceptance remain open.

## Development Automation

VerityCX's GitHub issue automation is configured under [`.symphony-plus/`](.symphony-plus/README.md).
That guide explains the repository-owned Symphony Plus workflow, startup command, issue commands,
workspace isolation, and Spec Kit boundary.

## Prerequisites

- Python 3.12, selected automatically by uv from `.python-version`
- uv 0.12.5
- Git 2.34 or newer
- Internet access for the first official acquisition only

Feature 001 acquisition needs no credentials. Feature 002 requires native PostgreSQL 18.6 and local
demo authentication; its deterministic provider needs no paid account. OpenAI and LangSmith
credentials are used only by explicitly enabled live execution/export.

## Run the Local App

On Linux/WSL, use the maintained bootstrap from the repository root:

```bash
uv run python scripts/setup_support_local.py --app
```

This starts the owned PostgreSQL cluster, provisions separate app and test databases,
applies migrations, creates or reuses demo authentication, and fills missing or empty
app settings in the ignored root `.env`. No manual SQL or password copying is needed.
Reruns preserve app credentials and existing nonempty settings; conflicting configuration
fails with a value-free category. Existing unregistered app databases/roles are not adopted.
The default command without `--app` retains its test-only behavior.

If setup reports `corpus=approval_required`, prepare the synthetic documents, review the
summary, and approve the printed hash explicitly:

```bash
uv run python scripts/manage_support.py corpus prepare --mode synthetic
uv run python scripts/manage_support.py corpus approve --hash HASH
```

Replace `HASH` with the printed digest. An already approved, unchanged collection needs no
further action. Setup never approves documents or enables paid provider calls.

For the customer page, build the frontend and run the API and worker together:

```bash
uv run python scripts/run_support.py --provider openai --build
```

This requires Node.js 24 and a valid server-side `OPENAI_API_KEY`. The launcher installs
locked frontend dependencies if missing, builds the page, verifies readiness, and owns
both child processes. Ctrl+C stops only those children. It refuses an occupied API port;
it never kills an existing service. Use `--setup` to run the app database bootstrap first,
or `--provider deterministic` for explicitly offline authored-fixture behavior.

Check `curl --fail-with-body http://127.0.0.1:8000/health/ready` for `{"status":"ready"}`.
Open `http://127.0.0.1:8000/` for the branded banking support page. Its customer messenger
uses a configured Chatwoot widget; without Chatwoot it truthfully shows chat unavailable.
There are no interactive API docs. The standalone
[HTTP contract](specs/002-durable-knowledge-support/contracts/http-api.md) remains available
using the generated local client credentials.

### Connect the Chatwoot customer messenger

The [local Chatwoot guide](docs/chatwoot-local-setup.md) documents Docker requirements,
private administrator credentials, a signed AgentBot connection, and real acceptance gates.
For an isolated local Linux Docker setup:

```bash
uv run python scripts/setup_chatwoot.py --allow-local-webhooks
```

This explicit flag permits private-network webhook callbacks inside the owned local
Chatwoot deployment. The helper starts separate Chatwoot PostgreSQL/Redis services,
creates the synthetic demo inbox and bot, fills missing integration settings, and runs
the independent integration migration. Restart the app launcher afterward. Hosted
Chatwoot requires equivalent verified configuration, one AgentBot in the configured account,
and a reachable authenticated webhook. Accounts with multiple AgentBots are unsupported.
OpenAI and Chatwoot API secrets never enter the frontend; only the public origin and
website token are exposed by `/chat/config`.

Run the setup command again after a reboot to start PostgreSQL and verify the configuration.
`uv run python scripts/setup_support_local.py --app --check` checks local files without
starting services, connecting to the database, or writing credentials. It does not replace
the HTTP readiness check.

## Local Environment Configuration

Copy `.env.example` to the ignored root `.env` and fill only the settings needed by the command you
intend to run. Maintained API, worker, management, validation, and pytest entry points load that one
absolute root file; values already exported by the invoking process always win. A missing `.env` is
supported and preserves each command's existing missing-configuration result.

The example contains every and only these VerityCX-owned names: `VERITYCX_DATABASE_URL`,
`VERITYCX_AUTH_FILE`, `VERITYCX_MIGRATION_DATABASE_URL`, `VERITYCX_TEST_DATABASE_URL`,
`VERITYCX_TEST_MIGRATION_DATABASE_URL`, `VERITYCX_VALIDATION_PROVIDER`,
`VERITYCX_VALIDATION_CORPUS`, `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`,
`VERITYCX_CHATWOOT_URL`, `VERITYCX_CHATWOOT_ACCOUNT_ID`, `VERITYCX_CHATWOOT_INBOX_ID`,
`VERITYCX_CHATWOOT_WEBSITE_TOKEN`, `VERITYCX_CHATWOOT_API_TOKEN`,
`VERITYCX_CHATWOOT_BOT_TOKEN`, and `VERITYCX_CHATWOOT_WEBHOOK_SECRET`. Host,
shell, Git, package, virtual-environment, PostgreSQL bootstrap, and CI controls remain externally
owned. Keep example values empty or unmistakably synthetic; never place a usable credential, DSN,
password, private path, or token in the tracked template.

Run the value-blind drift check from the Git root:

```text
uv run python scripts/check_environment_contract.py
```

Success prints `environment_contract_ok`. Failure prints sorted categories and names only. Fix the
maintained source read or `.env.example` entry named by the diagnostic; the checker never opens the
real `.env` or prints configured values.

## Acquire the Pinned Checkout

Run the single setup entry point from the project root:

```text
uv run python scripts/setup_tau3_data.py
```

The command loads the fixed reviewed values from `config/tau3-bench.toml`, clones through a unique
invocation-owned staging directory, verifies the exact origin, `v1.0.1` tag, commit
`fc0055dc4e0a316c3f83133267fbd6faaa770992`, clean Git state, and required banking paths, and only
then promotes the checkout to `.cache/tau3-bench/`.

Success output contains only:

```text
status: valid
mode: installed|existing
checkout: .cache/tau3-bench/
tag: v1.0.1
commit: fc0055dc4e0a316c3f83133267fbd6faaa770992
```

The cache, setup lock, and staging directories are ignored by Git. Upstream source and data remain
external and must never be copied into tracked VerityCX paths.

## Read-Only Validation

```text
uv run python scripts/setup_tau3_data.py --check
```

`--check` validates an existing checkout without network access or intentional filesystem
mutation. A missing checkout fails with `checkout-missing` and directs the developer to run the
default setup command.

## Failure and Recovery

Expected operational failures return exit code `1` and one categorized diagnostic on stderr,
without a traceback. Setup never fetches, resets, repairs, replaces, or deletes an existing
checkout. A surviving lock or staging directory is preserved for manual review because a later
invocation cannot prove ownership.

Git subprocesses use a fixed `core.autocrlf=input` policy: existing CRLF text and LF text are
compared using Git's text normalization, while fresh clones are not converted to CRLF. Binary
files and explicit `-text` attributes retain byte-sensitive checks. Real edits, staged changes,
and untracked files still fail validation. No cache files or user Git settings are rewritten.

## Development Verification

```text
uv lock --check
uv sync --locked
uv run python scripts/check_environment_contract.py
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy --strict src scripts tests
uv run pytest tests -m "not support_db and not live"
```

For full offline Feature 002 coverage on Linux/WSL, bootstrap the ignored, project-owned PostgreSQL
18.6 test cluster and load its generated environment in the current terminal:

```text
uv run python scripts/setup_support_local.py
source .cache/support/local/test.env
output=$(uv run python scripts/manage_support.py corpus prepare --mode synthetic)
hash=${output##*hash=}
uv run python scripts/manage_support.py corpus approve --hash "$hash"
uv run pytest tests -m "not live"
```

Tests create only temporary local Git repositories and runtime-generated synthetic canaries. They
must never acquire the official upstream checkout or commit upstream content. Root-command tests
prevent reintroducing a nested project. The complete Markdown/YAML and CI verification commands
are in the [Spec Kit quickstart](specs/001-acquire-tau3-banking/quickstart.md).

## Project Areas

- `config/`: reviewed immutable dependency configuration
- `scripts/`: thin project-root developer commands
- `src/veritycx/`: reusable strictly typed implementation
- `tests/`: repository-root command checks and network-independent data-source safety tests
- `docs/`: current data policy and explicitly future platform vision
- `.specify/` and `.agents/skills/`: GitHub Spec Kit constitution, templates, workflow, and skills
- `.symphony-plus/`: Symphony Plus workflow configuration and operator guide
- `.github/workflows/`: root-level quality gates on Windows, Linux, and macOS
- `specs/001-acquire-tau3-banking/`: specification, contracts, plan, tasks, and validation guide

## Safe Inspection and Data Use

```text
uv run python scripts/inspect_tau3_banking_data.py
```

Inspection validates twice before printing the tag, commit, recursive document/task counts, and
sorted top-level database shapes. It prints no filenames, bodies, nested records, task semantics, or
evaluation content. Only the configured documents subtree and exactly `db.json` are application-safe;
tasks and every unclassified path are default-denied and evaluation-only.

See [the τ³-Banking data policy](docs/data/tau3-banking.md) and
[third-party notices](THIRD_PARTY_NOTICES.md). Feature 001 explicitly excludes chunking, embeddings,
database import, agents, APIs, containers, and evaluation.
