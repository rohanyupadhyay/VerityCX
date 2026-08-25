<!-- Provides end-to-end implementation validation steps for Feature 001. -->
# Quickstart: Validate τ³-Banking Acquisition

This guide describes the expected developer workflow after Feature 001 is implemented. Run commands from the VerityCX repository root unless a scenario explicitly changes the current directory to prove root independence.

## Prerequisites

- Git is installed and available on `PATH`.
- uv is installed.
- Internet access is available for the first official acquisition only.
- No API key, `.env` secret, or paid service is required.

Python does not need to be preselected in the invoking shell: `.python-version` and `pyproject.toml` direct uv to Python 3.12.

## 1. Prepare the Locked Development Environment

```text
uv lock --check
uv sync --locked
```

Expected result: uv selects Python 3.12, installs the editable `veritycx` package and development tools, and makes no lockfile changes.

## 2. Acquire and Validate the Official Checkout

```text
uv run python scripts/setup_tau3_data.py
```

Expected result on a clean clone:

- the command clones the configured `v1.0.1` tag through a unique staging directory beneath `.cache/`;
- it validates origin, exact `HEAD`, tag binding, clean status, required banking paths, readability, and `db.json` structure;
- only after complete validation, `.cache/tau3-bench/` appears;
- stdout reports `mode: installed`, tag `v1.0.1`, and commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`;
- no API key is requested and no upstream file is added to Git tracking.

If any existing `.cache/tau3-bench/` path is invalid, setup exits with code `1`, reports the precise category on stderr, and leaves it untouched.

## 3. Prove Idempotency and Read-Only Validation

Run setup again:

```text
uv run python scripts/setup_tau3_data.py
```

Expected result: stdout reports `mode: existing`; the command performs no clone, fetch, reset, repair, or checkout change.

Then run explicit validation:

```text
uv run python scripts/setup_tau3_data.py --check
```

Expected result: stdout reports `mode: check`. The command creates no cache, lock, or staging state and performs no intentional filesystem mutation. When the checkout is absent, it fails with `error[checkout-missing]` and directs the developer to run setup without `--check`.

## 4. Inspect Safe Banking Metadata

```text
uv run python scripts/inspect_tau3_banking_data.py
```

Expected output contains only:

- checked-out tag;
- exact commit SHA;
- recursive document-file count;
- recursive task-file count;
- sorted top-level synthetic database collection names, JSON kinds, and direct counts for object/array collections.

Expected output never contains document bodies or filenames, nested synthetic records, task filenames or contents, prompts, grading criteria, reference actions, or expected answers. See [inspection-cli.md](contracts/inspection-cli.md) and [data-use-policy.md](contracts/data-use-policy.md).

## 5. Run Network-Independent Tests

```text
uv run pytest tests/data_sources/test_tau3.py
```

Expected result: all tests use temporary local Git repositories and generated synthetic JSON/files. No test reaches GitHub, requires an API key, or commits upstream τ³ content.

The suite proves:

- successful staged setup and validated promotion;
- offline/idempotent rerun and `--check` behavior;
- wrong origin, wrong SHA, wrong tag binding, and dirty-checkout rejection;
- incomplete/unreadable data and malformed database rejection;
- failed-clone cleanup limited to current-run staging;
- safe handling of files, symbolic links, junctions where supported, stale state, and changed current directories;
- absence of document, customer-record, and evaluation canaries from every inspection output channel.

## 6. Run Required Lint Verification

```text
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
```

Expected result: no diagnostics.

## 7. Run Constitution Quality Gates

```text
uv run ruff format --check src scripts tests
uv run mypy --strict src scripts tests
```

Expected result: deterministic formatting and strict typing pass for the reusable module, scripts, and tests. Ruff's configured docstring rules also check file-level and callable documentation.

## 8. Confirm Version-Control Isolation

```text
git status --short
git check-ignore -v .cache/tau3-bench/
```

Expected result: no acquired τ³ content is tracked, and the ignore rule resolves to `.cache/tau3-bench/`. Setup staging and lock patterns are ignored separately without ignoring unrelated files.

## Required Verification Set

The implementation plan preserves these requested commands exactly:

```text
uv run pytest tests/data_sources/test_tau3.py
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
uv run python scripts/setup_tau3_data.py --check
uv run python scripts/inspect_tau3_banking_data.py
```

On a new clone, run `uv run python scripts/setup_tau3_data.py` before the two live-checkout commands.

## Data-Use Reminder

Application-safe inputs are limited to:

- `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/`
- `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json`

Everything beneath `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/`, plus task aggregates and equivalent evaluation semantics elsewhere upstream, remains evaluation-only and must never enter prompts, indexes, runtime agents, application loaders, or APIs.
