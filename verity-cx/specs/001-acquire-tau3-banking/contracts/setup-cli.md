<!-- Defines the public setup and read-only validation command behavior for Feature 001. -->
# Contract: τ³-Banking Setup CLI

## Commands

```text
uv run python scripts/setup_tau3_data.py
uv run python scripts/setup_tau3_data.py --check
```

No other production options are planned. Argparse help and usage remain available through standard `-h`/`--help` behavior.

## Exit Codes and Streams

| Code | Meaning |
|---|---|
| `0` | A new checkout was installed and validated, an existing checkout was already valid, or `--check` validation passed. |
| `1` | Expected operational failure such as unavailable Git, clone failure, invalid target, provenance/revision mismatch, dirty checkout, invalid banking data, or staging conflict. |
| `2` | Command-line usage error produced by argparse. |

Successful summaries go to stdout. Expected diagnostics go to stderr without a traceback. The command MUST NOT print document bodies, database records, task contents, checkout-status filenames, or raw subprocess commands.

## Mode Matrix

| Target state | Default setup | `--check` |
|---|---|---|
| Missing | Claim lock, stage, clone, validate, and promote | Fail `checkout-missing`; create nothing |
| Valid and clean | Validate and return success; no lock or network | Validate and return success; no lock or network |
| Invalid or unexpected | Fail with precise category; preserve unchanged | Fail with precise category; preserve unchanged |
| Concurrent supported setup | One process owns lock; other fails `setup-locked` without cleanup of owner's state | Not applicable because check mode creates no lock |

## Required Git Invocations

All invocations use argument arrays and `shell=False`. Validation commands execute with the checkout as `cwd` and with optional locks disabled.

```text
git --version
git clone --no-local --branch v1.0.1 --single-branch -- https://github.com/sierra-research/tau2-bench.git <staging-parent>/checkout
git rev-parse --show-toplevel
git config --local --get-all remote.origin.url
git rev-parse HEAD
git rev-parse --verify refs/tags/v1.0.1^{commit}
git --no-optional-locks status --porcelain=v1 --untracked-files=all
```

`GIT_TERMINAL_PROMPT=0` is set for clone and Git validation. `GIT_OPTIONAL_LOCKS=0` is set for read-only validation as a belt-and-suspenders equivalent to the global option.

## Validation Order

1. Classify checkout path without following it; reject missing in validation mode, files, links, junctions, special objects, and unreadable directories.
2. Require `rev-parse --show-toplevel` to refer to the checkout itself, not an ancestor repository.
3. Require exactly one local `remote.origin.url` and exact equality with the configured `.git` URL.
4. Require `git rev-parse HEAD` to equal `fc0055dc4e0a316c3f83133267fbd6faaa770992`.
5. Require the peeled `v1.0.1` tag to resolve to the same SHA.
6. Require empty no-optional-locks porcelain output.
7. Require the exact configured documents directory, database file, and tasks directory to be contained, correct-kind, readable, and non-empty where applicable.
8. Require `db.json` to decode as UTF-8 JSON with a non-empty object at the top level.

The same validator runs for staged, existing, check-only, and inspection flows.

## Installation Transaction

1. Existing-target classification and validation occur before cache creation.
2. A first install creates or validates the real `.cache/` directory.
3. Atomic directory creation claims `.cache/tau3-bench.setup.lock/`; only the creator records ownership.
4. Target absence is rechecked after lock acquisition.
5. `tempfile.mkdtemp(prefix="tau3-bench-staging-", dir=cache_root)` creates one current-run-owned absolute parent. Git clones into its nonexistent `checkout/` child.
6. Complete Git and banking validation succeeds before promotion.
7. Cleanliness and destination absence are rechecked immediately before a same-filesystem `os.rename`/`Path.rename` operation that does not request replacement.
8. The final checkout is validated before success is reported.
9. `finally` removes only the exact owned staging parent and lock. It never globs, deletes stale state, repairs a checkout, or deletes/replaces the final target.

## Success Output

The stable field set is:

```text
status: valid
mode: installed|existing|check
checkout: .cache/tau3-bench/
tag: v1.0.1
commit: fc0055dc4e0a316c3f83133267fbd6faaa770992
```

No file counts or data samples are required from setup; those belong to inspection.

## Diagnostic Categories

| Category | Required information |
|---|---|
| `git-unavailable` | Git prerequisite and recovery action. |
| `checkout-missing` | Expected checkout and command to run without `--check`. |
| `unexpected-target` | Configured target and detected kind; no automatic action. |
| `not-standalone-repository` | Expected checkout root and detected Git top level. |
| `origin-mismatch` | Expected and detected origin; no credentials or command dump. |
| `revision-mismatch` | Expected and detected full SHA. |
| `tag-mismatch` | Expected tag/SHA and detected resolution or absence. |
| `dirty-checkout` | Presence/category/count of changes, never filenames or porcelain text. |
| `banking-data-invalid` | Exact configured required path and missing/empty/wrong-kind/readability reason. |
| `malformed-database` | `db.json` and JSON line/column or top-level shape reason, never source text. |
| `setup-locked` | Lock location and manual-review guidance; never remove it automatically. |
| `clone-failed` | Git exit code and sanitized concise stderr. |
| `destination-conflict` | Final target appeared and was preserved. |
| `staging-cleanup-failed` | Exact current-run staging path retained for manual cleanup. |
