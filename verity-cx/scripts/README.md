<!-- Documents the developer command module and its operational contracts. -->

# Developer Commands

## Purpose and Structure

`scripts/` contains thin, project-root-resolving entry points for the τ³-Banking dependency:

- `setup_tau3_data.py` installs or validates the exact configured checkout.
- `inspect_tau3_banking_data.py` reports only approved aggregate metadata from an existing checkout.

Both scripts depend on `veritycx.data_sources.tau3`, Python 3.12, the fixed TOML configuration, and
Git 2.34 or newer. They expose no source, revision, path, credential, or configuration overrides.

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
`error[category]: message` line on stderr and exit `1`; invalid usage is argparse exit `2`. No
expected failure emits a traceback or partial success output. Diagnostics contain recovery guidance
but exclude credentials, Git commands/status, descendant filenames, and source-derived content.

Verify both interfaces with:

```text
uv run pytest tests/data_sources/test_tau3.py
uv run ruff check scripts
uv run mypy --strict scripts
```
