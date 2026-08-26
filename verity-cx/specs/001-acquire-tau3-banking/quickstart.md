<!-- Provides end-to-end implementation validation steps for Feature 001. -->

# Quickstart: Validate τ³-Banking Acquisition

This guide describes the expected developer workflow after Feature 001 is implemented. Run commands from the nested VerityCX project root (`verity-cx/`) unless a scenario explicitly changes the current directory to prove root independence. The outer directory containing `.git` is the Git root and owns `.github/workflows/`.

## Prerequisites

- Git 2.34 or newer is installed and available on `PATH`.
- uv 0.12.5 is installed; required CI pins this exact version.
- Internet access is available for the first official acquisition only.
- No API key, `.env` secret, or paid service is required.
- The required verification matrix uses Python 3.12 on `ubuntu-latest`, `windows-latest`, and `macos-latest` GitHub-hosted runners.

Python does not need to be preselected in the invoking shell: `.python-version` and `pyproject.toml` direct uv to Python 3.12.

Record `git --version` and `uv --version` before verification. The repository path must be representable and accessible to Python and Git under the host's path-length, filesystem, and permission rules.

## 1. Prepare the Locked Development Environment

```text
uv lock --check
uv sync --locked
```

Expected result: uv selects Python 3.12, installs the editable `veritycx` package and development tools, and makes no lockfile changes.

## 2. Run the Official Live Smoke Test

This one-environment manual smoke test acquires and validates the fixed official upstream pin. It is not part of the network-independent CI matrix.

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

SC-001 measures the network-independent first-acquisition test from setup-process start through successful exit. The wall-clock result must remain under 10 minutes on each required runner. Existing-checkout validation and inspection durations are recorded for diagnostics but have no separate machine-dependent threshold.

The suite proves:

- successful staged setup and validated promotion;
- offline/idempotent rerun and `--check` behavior;
- wrong origin, wrong SHA, wrong tag binding, and dirty-checkout rejection;
- incomplete/unreadable data and malformed database rejection;
- failed-clone cleanup limited to current-run staging;
- interrupted-run recovery that preserves surviving lock and stale staging state and reports manual recovery guidance;
- safe handling of files, symbolic links, junctions where supported, stale state, and changed current directories;
- preservation of bytes, object/link identity, exposed permissions, Git state, and neighboring cache entries in conflict cases;
- final inspection revalidation rejects a detected concurrent state/count/shape change without partial stdout;
- absence of document, customer-record, and evaluation canaries from every result, error, representation, and serialization channel.

## 6. Run Required Lint Verification

```text
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
```

Expected result: no diagnostics.

## 7. Run Constitution Quality Gates

```text
uv run ruff format --check src scripts tests
uv run mdformat --check README.md THIRD_PARTY_NOTICES.md config/README.md docs/data/tau3-banking.md
uv run mdformat --check scripts/README.md src/veritycx/README.md src/veritycx/data_sources/README.md tests/data_sources/README.md
uv run mdformat --check specs/001-acquire-tau3-banking/spec.md specs/001-acquire-tau3-banking/plan.md specs/001-acquire-tau3-banking/research.md specs/001-acquire-tau3-banking/data-model.md specs/001-acquire-tau3-banking/quickstart.md specs/001-acquire-tau3-banking/tasks.md
uv run mdformat --check specs/001-acquire-tau3-banking/contracts/configuration.md specs/001-acquire-tau3-banking/contracts/data-use-policy.md specs/001-acquire-tau3-banking/contracts/inspection-cli.md specs/001-acquire-tau3-banking/contracts/setup-cli.md ../.github/workflows/README.md
uv run yamlfix --check ../.github/workflows/quality.yml
uv run mypy --strict src scripts tests
```

Expected result: deterministic Python, maintained-Markdown, and workflow-YAML formatting plus strict typing pass. Ruff's configured docstring rules also check file-level and callable documentation. The explicit Markdown list avoids recursively formatting `.agents/`, `.specify/`, generated, vendored, or unrelated files.

## 8. Verify the Required CI Matrix

The Git-root `.github/workflows/quality.yml`, addressed as `../.github/workflows/quality.yml` from the project root, must set `verity-cx` as the working directory and run required Python 3.12 jobs on `ubuntu-latest`, `windows-latest`, and `macos-latest`. Each job pins uv 0.12.5, requires Git 2.34 or newer, records the runner image and Python/Git/uv versions, records the first-acquisition duration, and runs lock verification, locked synchronization, Ruff format and lint checks, mdformat, yamlfix, strict mypy, and the network-independent pytest suite. CI must not acquire the live upstream repository, and every matrix job must pass before merge.

## 9. Confirm Version-Control Isolation

```text
git status --short
git check-ignore -v .cache/tau3-bench/
git ls-files -- .cache/tau3-bench/
```

Expected result: `git ls-files` prints nothing and the ignore rule resolves to `.cache/tau3-bench/`. For the tracked-change audit, record the baseline and candidate commit SHAs, run `git diff --name-status BASELINE_COMMIT..CANDIDATE_COMMIT` after substituting those recorded SHAs, confirm every changed path is within the planned file responsibilities, and review every non-generated addition for upstream-derived source, data, or evaluation content. Record all reviewed paths, reviewer, date, and an explicit pass/fail result without reproducing upstream contents. Setup staging and lock patterns remain ignored separately without ignoring unrelated files.

## Verification Evidence: 2026-08-26

### Local and Official Smoke

- Reviewer/environment: Codex on Windows, Python 3.12.14 under uv, Git 2.51.2, uv
  0.12.5.
- Locked environment, Ruff format/lint, all maintained Markdown, workflow YAML, strict mypy,
  and the network-independent test suite passed locally.
- Test result: 60 passed and one capability-only symbolic-link test skipped because the Windows
  account lacked link-creation privilege; shared injected reparse-point rejection passed.
- Official first acquisition passed at the configured tag and SHA in 59.535 seconds.
- Offline-proxy reruns passed: existing 2.011 seconds, check 2.005 seconds, and inspection 3.758
  seconds. These three durations are diagnostic and non-normative.
- Independent safe enumeration matched inspection at 698 document files, 97 task files, and all 17
  reported top-level object shapes. No body, nested key/value, filename, or task semantic was
  recorded.
- The three GitHub-hosted operating-system jobs remain pending until this committed candidate is
  pushed and the required workflow runs; local evidence does not substitute for SC-001/SC-002.

### SC-007 Tracked-Content Audit

- Baseline commit: `20cdf23afcd064ef4cdcfb9d58bfff8c462854f6`
- Candidate commit: `21364d826bd5e45ef0a40783129662ab8bb0f3f7`
- Reviewer: Codex
- Review date: 2026-08-26
- `git ls-files -- .cache/tau3-bench/`: zero paths.
- `git check-ignore -v .cache/tau3-bench/`: resolved to
  `verity-cx/.gitignore:13:.cache/tau3-bench/`.
- Result: **PASS**. All 32 changed paths are project-owned and fall within the planned Feature 001
  specification, implementation, tests, documentation, configuration, dependency-lock, or CI
  responsibilities. Every non-generated addition was reviewed; `uv.lock` was reviewed as generated
  dependency metadata. No acquired upstream source, data, or evaluation content occurs in the
  tracked diff.

Complete reviewed path set:

```text
.github/workflows/README.md
.github/workflows/quality.yml
verity-cx/.gitignore
verity-cx/.python-version
verity-cx/README.md
verity-cx/THIRD_PARTY_NOTICES.md
verity-cx/config/README.md
verity-cx/config/tau3-bench.toml
verity-cx/docs/data/tau3-banking.md
verity-cx/pyproject.toml
verity-cx/scripts/README.md
verity-cx/scripts/inspect_tau3_banking_data.py
verity-cx/scripts/setup_tau3_data.py
verity-cx/specs/001-acquire-tau3-banking/checklists/comprehensive.md
verity-cx/specs/001-acquire-tau3-banking/contracts/configuration.md
verity-cx/specs/001-acquire-tau3-banking/contracts/data-use-policy.md
verity-cx/specs/001-acquire-tau3-banking/contracts/inspection-cli.md
verity-cx/specs/001-acquire-tau3-banking/contracts/setup-cli.md
verity-cx/specs/001-acquire-tau3-banking/data-model.md
verity-cx/specs/001-acquire-tau3-banking/plan.md
verity-cx/specs/001-acquire-tau3-banking/quickstart.md
verity-cx/specs/001-acquire-tau3-banking/research.md
verity-cx/specs/001-acquire-tau3-banking/spec.md
verity-cx/specs/001-acquire-tau3-banking/tasks.md
verity-cx/src/veritycx/README.md
verity-cx/src/veritycx/__init__.py
verity-cx/src/veritycx/data_sources/README.md
verity-cx/src/veritycx/data_sources/__init__.py
verity-cx/src/veritycx/data_sources/tau3.py
verity-cx/tests/data_sources/README.md
verity-cx/tests/data_sources/test_tau3.py
verity-cx/uv.lock
```

### SC-008 Documentation Review

Result: **PASS**. Without implementation code, `README.md`, `docs/data/tau3-banking.md`, and
`THIRD_PARTY_NOTICES.md` identify Sierra Research, the official URL, MIT licence, tag, SHA,
setup/check/inspection usage, the documents and database allow-list, the task and unclassified-path
deny-list, and the feature exclusions.

## Required Verification Set

The implementation plan preserves these requested commands exactly:

```text
uv run pytest tests/data_sources/test_tau3.py
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
uv run python scripts/setup_tau3_data.py --check
uv run python scripts/inspect_tau3_banking_data.py
```

On a new clone, run `uv run python scripts/setup_tau3_data.py` from the project root before the two live-checkout commands.

## Data-Use Reminder

Application-safe inputs are limited to:

- `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/`
- `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json`

Everything beneath `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/`, plus task aggregates and equivalent evaluation semantics elsewhere upstream, remains evaluation-only and must never enter prompts, indexes, runtime agents, application loaders, or APIs.
