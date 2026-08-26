<!-- Documents the VerityCX project purpose, setup workflow, and quality gates. -->

# VerityCX

VerityCX is a Python 3.12 project for reproducible customer-experience research tooling. Feature
001 provides developer-only acquisition and validation of the external τ³-Banking dataset. It
does not import that data into the application or build retrieval, agent, API, container, or
evaluation behavior.

## Prerequisites

- Python 3.12, selected automatically by uv from `.python-version`
- uv 0.12.5
- Git 2.34 or newer
- Internet access for the first official acquisition only

No API key, credential, paid service, or environment override is supported.

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

## Development Verification

```text
uv lock --check
uv sync --locked
uv run ruff format --check src scripts tests
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
uv run mypy --strict src scripts tests
uv run pytest tests/data_sources/test_tau3.py
```

Tests create only temporary local Git repositories and runtime-generated synthetic canaries. They
must never acquire the official upstream checkout or commit upstream content.

## Project Areas

- `config/`: reviewed immutable dependency configuration
- `scripts/`: thin project-root developer commands
- `src/veritycx/`: reusable strictly typed implementation
- `tests/data_sources/`: network-independent Git, filesystem, and disclosure tests
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
