<!-- Provides end-to-end implementation validation steps for Feature 001. -->

# Quickstart: Validate τ³-Banking Acquisition

Run every command in this guide from the Git repository root, which is also the sole project root. Python metadata, scripts, tests, `.specify/`, `.agents/skills/`, and `.github/workflows/` live there. Optional absolute-path scenarios prove caller-directory independence; no directory change is required for the normal workflow.

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
uv run pytest tests
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
uv run ruff check src scripts tests
```

Expected result: no diagnostics.

## 7. Run Constitution Quality Gates

```text
uv run ruff format --check src scripts tests
uv run mdformat --check README.md THIRD_PARTY_NOTICES.md config/README.md docs/data/tau3-banking.md
uv run mdformat --check .specify/memory/constitution.md docs/README.md docs/project-vision.md tests/README.md
uv run mdformat --check scripts/README.md src/veritycx/README.md src/veritycx/data_sources/README.md tests/data_sources/README.md
uv run mdformat --check specs/001-acquire-tau3-banking/spec.md specs/001-acquire-tau3-banking/plan.md specs/001-acquire-tau3-banking/research.md specs/001-acquire-tau3-banking/data-model.md specs/001-acquire-tau3-banking/quickstart.md specs/001-acquire-tau3-banking/tasks.md
uv run mdformat --check specs/001-acquire-tau3-banking/contracts/configuration.md specs/001-acquire-tau3-banking/contracts/data-use-policy.md specs/001-acquire-tau3-banking/contracts/inspection-cli.md specs/001-acquire-tau3-banking/contracts/setup-cli.md .github/workflows/README.md
uv run mdformat --check specs/001-acquire-tau3-banking/checklists/comprehensive.md specs/001-acquire-tau3-banking/checklists/requirements.md
uv run yamlfix --check .github/workflows/quality.yml
git check-attr eol -- README.md specs/001-acquire-tau3-banking/tasks.md .github/workflows/README.md .github/workflows/quality.yml
uv run mypy --strict src scripts tests
```

Expected result: deterministic Python, maintained-Markdown, and workflow-YAML formatting plus strict typing pass. The Git attribute command reports `eol: lf` for all four representative paths, proving formatter-owned project and Git-root text share one checkout representation on Windows, Linux, and macOS. Ruff's configured docstring rules also check file-level and callable documentation. The explicit Markdown list avoids recursively formatting `.agents/`, `.specify/`, generated, vendored, or unrelated files.

## 8. Verify the Required CI Matrix

The root `.github/workflows/quality.yml` must set `.` as the working directory and run required Python 3.12 jobs on `ubuntu-latest`, `windows-latest`, and `macos-latest`. The Git-root `.gitattributes` must pin formatter-owned Markdown and YAML to LF, and each job must verify representative project and workflow paths resolve to that attribute before formatting. Each job pins uv 0.12.5, requires Git 2.34 or newer, records the matrix label, runner name/OS/architecture, actual hosted `ImageOS`/`ImageVersion`, and Python/Git/uv versions, and fails if the monotonic first-acquisition measurement is 600 seconds or more. It also runs lock verification, locked synchronization, Ruff format and lint checks, mdformat, yamlfix, strict mypy, and the network-independent pytest suite. CI must not acquire the live upstream repository, and every matrix job must pass before merge.

## 9. Confirm Version-Control Isolation

```text
git status --short
git check-ignore -v .cache/tau3-bench/
git ls-files -- .cache/tau3-bench/
```

Expected result: `git ls-files` prints nothing and the ignore rule resolves to `.cache/tau3-bench/`. For the tracked-change audit, record the baseline and candidate commit SHAs, run `git diff --name-status BASELINE_COMMIT..CANDIDATE_COMMIT` after substituting those recorded SHAs, confirm every changed path—including the Git-root `.gitattributes` quality control—is within the planned file responsibilities, and review every non-generated addition for upstream-derived source, data, or evaluation content. Record all reviewed paths, reviewer, date, and an explicit pass/fail result without reproducing upstream contents. Setup staging and lock patterns remain ignored separately without ignoring unrelated files.

## Historical Evidence (Before Root Migration)

The following dated records describe earlier candidates. Their `verity-cx/` paths identify files
at those historical commits, not current paths or instructions. Current commands above and below
use the single repository root.

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

## Pre-Commit Verification Evidence: 2026-09-02

- Candidate state: uncommitted implementation of T058 and T059; this evidence is not final SC-002 or
  SC-007 acceptance because no candidate commit SHA or hosted matrix run exists yet.
- Environment: Windows, Python 3.12.14 under uv, Git 2.51.2, and uv 0.12.5.
- Lock, locked sync, Ruff format/lint, maintained Markdown, workflow YAML, strict mypy, and Git LF
  attribute checks passed locally.
- Network-independent suite: 126 passed and three capability-only file-symbolic-link tests skipped;
  real Windows junction/reparse end-to-end cases passed.
- A process-owned clean temporary project exercised the current setup and inspection scripts against
  the official pin. Installation passed in 36.000 seconds, then offline-proxy existing setup passed
  in 1.922 seconds, `--check` in 1.906 seconds, and inspection in 3.672 seconds.
- Independent safe enumeration matched inspection at 698 document files, 97 task files, and all 17
  top-level database shapes. No body, nested key/value, filename, or task semantic was recorded.
- The existing checkout in the development project was dirty and was preserved without repair or
  replacement. Temporary smoke state was removed automatically after the comparison passed.
- Final acceptance still requires a committed candidate, a repeated SC-007 audit naming that SHA,
  and one clean passing hosted job on each required matrix runner with retained logs.

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

## Repository-Root Migration Evidence: 2026-09-09

This is local working-tree evidence for FR-023/FR-024 and SC-009, not final hosted CI or a
commit-to-commit SC-007 acceptance record. The baseline is
`7c5a92b18d33ae25fc2fe06ce47ca6b623a2cd83`; this migration has not been committed or pushed.

### Layout and Data Preservation

- The Git root now contains Python metadata, source, scripts, tests, config, documentation,
  specifications, `.specify/`, and `.agents/skills/`. There are no forwarding wrappers or duplicate
  Python projects. Both production scripts and all package implementation files moved unchanged.
- The root `README.md` is the implementation guide. The former extensionless README is preserved
  in `docs/project-vision.md`, explicitly labeled as future scope.
- The existing cache moved intact. A sorted manifest of cache-relative paths and file SHA-256
  hashes, including Git administrative files, contained 1,515 files before and after the move.
  Its aggregate SHA-256 was identical:
  `19AE17A84A638B23F0B920CE0D87B75F4EF8EFED32C68F56F7F2E30587DBB84A`.
- The old generated environment and tool caches remain in ignored `.cache/root-migration-backup/`.
  Root `uv sync --locked` created a fresh `.venv/` without changing `uv.lock`.
- No source or user data was deleted. The execution policy rejected even the non-recursive removal
  of the verified-empty old `verity-cx/` directory. It remains empty and is not a project root;
  T063 remains open only for this local housekeeping step. Git does not track empty directories.
- `git check-ignore -v` confirms the root cache, backup, and active environment are ignored;
  `git ls-files -- .cache/` returns zero paths. A separate temporary review index identifies the
  migration as renames plus scoped edits and passes `git diff --cached --check`; the user's actual
  index was not staged or changed.

### Root Commands and Automated Gates

- `tests/test_repository_layout.py` failed all three cases before the move because scripts could
  not be opened from Git's top level, then passed all three afterward.
- Every root README command was exercised at the Git root. Lock verification, locked sync,
  Ruff format/lint, strict mypy, and full pytest passed. All maintained Markdown checks, workflow
  YAML checks, and the four representative LF attributes passed as well.
- Full suite: **129 passed, 3 skipped** in 84.33 seconds on Windows/Python 3.12.14. The skips require
  file-symlink privileges (`WinError 1314`); available junction and injected safety cases passed.
- The full test run disabled global/system Git configuration. Before the fixture correction, the
  focused linked-path cases produced 2 failures, 2 passes, and 2 capability skips; afterward the
  full suite passed with cloned fixtures supplying their own local commit identity.
- Root `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`
  resolves `specs/001-acquire-tau3-banking` under the Git root. Root
  `.specify/scripts/powershell/resolve-template.ps1 constitution-template -Json` resolves the
  installed template. No extension hooks are configured.
- Main-cache setup, `--check`, and inspection each exit `1` with `dirty-checkout`, reporting 472
  tracked-change entries under the application's isolated Git settings. This pre-existing cache
  was not repaired. These are documented safety failures, not command-path failures.

### Successful Clean-Root Smoke

- An isolated Git root at `C:\Users\rohan\AppData\Local\Temp\vcxr-68299455` received the current
  Python metadata, config, source, and scripts, with no nested project or pre-existing cache.
- The exact root command `uv run python scripts/setup_tau3_data.py` installed the official pin
  in 84.746 seconds and returned `mode: installed`, tag `v1.0.1`, and commit
  `fc0055dc4e0a316c3f83133267fbd6faaa770992`. This networked duration is not the SC-001 CI metric.
- With HTTP/HTTPS proxies pointing to an unavailable local endpoint, root existing setup,
  `--check`, and inspection all returned `0` without a new download.
- Independent PowerShell enumeration and top-level JSON-shape derivation matched inspection:
  **698 documents, 97 tasks, 17 database collections**. No record values, bodies, task semantics,
  or individual source filenames were recorded.
- The temporary smoke root is retained for inspection; no cleanup or deletion was performed.

### Spec Kit Consistency and Independent Review

Read-only analysis covered 24 functional requirements, 9 success criteria, 65 tasks, and all six
constitutional principles. Every requirement/success criterion has task coverage; no unmapped
tasks, unresolved root-policy contradictions, or critical artifact issues were identified. The
added requirements map to T062-T065; older acceptance work remains represented by its existing
tasks. Historical paths are explicitly labeled and are not current instructions.

An independent read-only reviewer found no blocking migration defects and confirmed root CLI
parsers, Spec Kit feature/template resolution, package installation, ignore rules, relative links,
and review-index whitespace checks. The maintained-document link check covered 24 Markdown files
and 20 local links with no broken targets. This is local review, not a substitute for hosted CI.

### Remaining Acceptance Gates

T048, T057, T059, and T060 still require their recorded clean hosted three-OS evidence and final
candidate-specific acceptance/audit. Local migration checks do not close those gates. T063's only
remaining migration action is removal of the empty local directory when permitted.
