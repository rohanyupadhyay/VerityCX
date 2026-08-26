<!-- Defines the public setup and read-only validation command behavior for Feature 001. -->

# Contract: τ³-Banking Setup CLI

## Commands

```text
uv run python scripts/setup_tau3_data.py
uv run python scripts/setup_tau3_data.py --check
```

No other production options are planned. Argparse help and usage remain available through standard `-h`/`--help` behavior.

Both forms resolve the project root from the script location and therefore have the same behavior when launched from any current working directory. Git 2.34 or newer and uv 0.12.5 are the supported command baseline.

When the caller is outside the project root, the equivalent absolute-path form is `uv run --project <absolute-project-root> --locked python <absolute-project-root>/scripts/setup_tau3_data.py [--check]`. The explicit uv project selection supplies the same locked package environment without changing the caller's working directory or modifying `PYTHONPATH`/`sys.path`.

## Exit Codes and Streams

| Code | Meaning |
|---|---|
| `0` | A new checkout was installed and validated, an existing checkout was already valid, or `--check` validation passed. |
| `1` | Expected operational failure such as unavailable Git, clone failure, invalid target, provenance/revision mismatch, dirty checkout, invalid banking data, or staging conflict. |
| `2` | Command-line usage error produced by argparse. |

Successful summaries go to stdout. Expected diagnostics go to stderr without a traceback. The command MUST NOT print document bodies, database records, task contents, checkout-status filenames, or raw subprocess commands.

Expected diagnostics use `error[category]: reason=...; path="..."; recovery=...`. The JSON-escaped `path` field is omitted only when no configured or current-run-owned path applies.

## Mode Matrix

| Target state | Default setup | `--check` |
|---|---|---|
| Missing | Claim lock, stage, clone, validate, and promote | Fail `checkout-missing`; create nothing |
| Valid and clean | Validate and return success; no lock or network | Validate and return success; no lock or network |
| Invalid or unexpected | Fail with precise category; preserve unchanged | Fail with precise category; preserve unchanged |
| Concurrent supported setup | One process owns lock; other fails `setup-locked` without cleanup of owner's state | Not applicable because check mode creates no lock |

Every existing-target row is offline: neither form contacts the remote, and both preserve target/cache bytes, object/link identity, exposed permissions, Git administrative/worktree state, and neighboring cache entries. Access timestamps caused by required reads are outside the preservation snapshot.

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
1. Require `rev-parse --show-toplevel` to refer to the checkout itself, not an ancestor repository.
1. Require exactly one local `remote.origin.url` and exact equality with the configured `.git` URL.
1. Require `git rev-parse HEAD` to equal `fc0055dc4e0a316c3f83133267fbd6faaa770992`.
1. Require the peeled `v1.0.1` tag to resolve to the same SHA.
1. Require empty no-optional-locks porcelain output.
1. Require the exact configured documents directory, database file, and tasks directory to be contained, correct-kind, readable, and non-empty where applicable.
1. Require `db.json` to decode as UTF-8 JSON with a non-empty object at the top level.

The same validator runs for staged, existing, check-only, and inspection flows.

## Installation Transaction

1. Existing-target classification and validation occur before cache creation.
1. A first install creates or validates the real `.cache/` directory.
1. Atomic directory creation claims `.cache/tau3-bench.setup.lock/`; only the creator records ownership.
1. Target absence is rechecked after lock acquisition.
1. `tempfile.mkdtemp(prefix="tau3-bench-staging-", dir=cache_root)` creates one current-run-owned absolute parent. Git clones into its nonexistent `checkout/` child.
1. Complete Git and banking validation succeeds before promotion.
1. Cleanliness and destination absence are rechecked immediately before a same-filesystem platform-native exclusive rename: Windows `os.rename`, Linux `renameat2(..., RENAME_NOREPLACE)`, or macOS `renamex_np(..., RENAME_EXCL)`. Unsupported exclusive-rename behavior fails closed.
1. The final checkout is validated before success is reported.
1. `finally` removes only the exact owned staging parent and lock. It never globs, deletes stale state, repairs a checkout, or deletes/replaces the final target.
1. A detected failure after promotion preserves the promoted checkout for manual review and reports the failure without rollback, repair, or replacement.

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
| `configuration-invalid` | Fixed configuration path, schema/field category, and correction action without echoing secrets or arbitrary values. |
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
| `checkout-changed` | Validation observations disagreed; no partial success output and manual retry/review guidance. |
| `staging-cleanup-failed` | Exact current-run staging path retained for manual cleanup. |

Every expected diagnostic uses exit code `1`, contains exactly one category, and includes only the configured/current-run-owned path, safe expected/detected metadata, and non-destructive recovery action applicable to that category. Diagnostics, exception text, logs, stdout/stderr, object representations, and supported serialization share the non-disclosure boundary.
