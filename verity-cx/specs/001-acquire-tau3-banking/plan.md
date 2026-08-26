<!-- Defines the implementation design and quality gates for Feature 001. -->

# Implementation Plan: Acquire τ³-Banking Data

**Branch**: `001-acquire-tau3-banking` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-acquire-tau3-banking/spec.md` plus the Python 3.12, uv, component, workflow, test, and verification constraints supplied to `$speckit-plan`.

## Summary

Build a minimal Python 3.12 developer-tooling package, managed by uv, that reads a single reviewed TOML pin, acquires `https://github.com/sierra-research/tau2-bench.git` at tag `v1.0.1`, verifies exact commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`, validates the required τ³-Banking paths, and promotes a validated staging checkout to `.cache/tau3-bench/` without altering any pre-existing target. Reusable typed logic lives in `src/veritycx/data_sources/tau3.py`; thin project-root scripts provide setup, read-only checking, and safe inspection. Tests use temporary local Git repositories and synthetic canary data so the suite is network-independent and proves that evaluation-only content never enters output.

## Technical Context

**Language/Version**: Python 3.12 only (`requires-python = ">=3.12,<3.13"` and `.python-version` set to `3.12`)

**Primary Dependencies**: Python standard library (`argparse`, `dataclasses`, `json`, `pathlib`, `subprocess`, `tempfile`, `tomllib`); Git CLI 2.34 or newer; uv 0.12.5 with `uv_build`; development-only pytest, Ruff, mypy, mdformat, and yamlfix

**Storage**: Read-only TOML configuration, an external Git working tree under `.cache/`, and upstream JSON files; no application database or import

**Testing**: pytest with temporary local working and bare Git repositories, generated sample files, subprocess-boundary tests, filesystem snapshots, and stdout/stderr canaries

**Target Platform**: Python 3.12 with Git and uv on the required `ubuntu-latest`, `windows-latest`, and `macos-latest` GitHub-hosted runner matrix; developers use the same command contract locally

**Project Type**: Minimal packaged Python library plus project-root command-line scripts and Git-root CI configuration

**Performance Goals**: The network-independent local-remote first-acquisition test completes within 10 minutes on every required runner, measured from setup-process start through successful exit. Existing-checkout validation and inspection durations are recorded diagnostically but have no separate machine-dependent threshold in Feature 001

**Constraints**: No API keys; no `shell=True`; no current-working-directory path resolution; no fetch/reset/repair of an existing checkout; no automatic deletion or overwrite of `.cache/tau3-bench/`; no document, customer-record, or evaluation-content output through any result/error channel; setup stages on the same filesystem as the target; `--check` performs no download or intentional filesystem mutation; inspection buffers output until a repeated final validation proves the checkout and approved shape are unchanged

**Scale/Scope**: One pinned public repository, one banking domain, one local checkout, and hundreds of small data files; no chunking, embeddings, database import, agents, APIs, containers, or evaluation execution

## Root Definitions

- **Git root**: The outer `VerityCX/` directory containing `.git` and owning
  `.github/workflows/`.
- **Project root**: The nested `VerityCX/verity-cx/` directory containing
  `pyproject.toml`, `src/`, `scripts/`, `config/`, `specs/`, and `.cache/`.
- Documented developer and verification examples run from the project root, while
  both public scripts behave identically from any current working directory.
  Production paths resolve from the project root derived from each script's
  `__file__`. Git-root CI steps set `verity-cx` as their working directory.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Planned evidence |
|---|---|---|
| I. Module Documentation Is Mandatory | PASS | Add the project-root `README.md`, the Git-root `.github/workflows/README.md`, and focused READMEs for `config/`, `src/veritycx/`, `src/veritycx/data_sources/`, `scripts/`, and `tests/data_sources/`; each documents purpose, boundaries, interfaces, dependencies, usage, tests, constraints, and failure modes. |
| II. File-Level Documentation Is Mandatory | PASS | Every maintained Python file starts with a module docstring; Markdown starts with an HTML comment; YAML, TOML, and `.gitignore` use leading native comments. Generated `uv.lock` and the tool-owned `.python-version` marker are exempt. |
| III. Code Interfaces and Decisions Are Documented | PASS | Every function, class, dataclass, and test has a typed signature and meaningful docstring. Safety-critical path containment, staging ownership, Git validation order, and evaluation-data denial receive rationale comments. |
| IV. Strict Typing Is Non-Negotiable | PASS | Mypy strict mode covers `src`, `scripts`, and `tests`; TOML, JSON, subprocess results, and filesystem entries are validated at typed boundaries without public `Any`, ignored diagnostics, or unchecked casts. |
| V. Formatting and Quality Gates Are Automated | PASS | Add a Git-root `.github/workflows/quality.yml` matrix workflow with project working directory `verity-cx`; every required job runs lock verification, locked synchronization, Ruff formatting and lint, mdformat for the explicit maintained-Markdown set, yamlfix for workflow YAML, strict mypy, and network-independent pytest. |

**Pre-design gate result**: PASS. No constitutional exception or complexity justification is required.

## Project Structure

### Documentation (this feature)

```text
specs/001-acquire-tau3-banking/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── configuration.md
│   ├── data-use-policy.md
│   ├── inspection-cli.md
│   └── setup-cli.md
└── tasks.md                    # Created later by $speckit-tasks
```

### Git and Project Structure

```text
VerityCX/                              # Git root
├── .github/
│   └── workflows/
│       ├── README.md
│       └── quality.yml
└── verity-cx/                         # Project root
    ├── .gitignore
    ├── .python-version
    ├── README.md
    ├── THIRD_PARTY_NOTICES.md
    ├── pyproject.toml
    ├── uv.lock
    ├── config/
    │   ├── README.md
    │   └── tau3-bench.toml
    ├── docs/
    │   └── data/
    │       └── tau3-banking.md
    ├── scripts/
    │   ├── README.md
    │   ├── inspect_tau3_banking_data.py
    │   └── setup_tau3_data.py
    ├── src/
    │   └── veritycx/
    │       ├── __init__.py
    │       ├── README.md
    │       └── data_sources/
    │           ├── __init__.py
    │           ├── README.md
    │           └── tau3.py
    └── tests/
        └── data_sources/
            ├── README.md
            └── test_tau3.py
```

Generated, ignored runtime state beneath the project root:

```text
.cache/
├── tau3-bench/                         # Validated final checkout
├── tau3-bench-staging-<unique>/        # Current-run-owned staging parent
└── tau3-bench.setup.lock/              # Cooperative setup lock
```

**Structure Decision**: Use one small `src`-layout package so both scripts import the same typed implementation under `uv run`, without `PYTHONPATH` or `sys.path` changes. Keep the requested implementation in one focused module while separating Git operations, banking-data validation/inspection, and setup orchestration through distinct typed functions and result models. Keep GitHub Actions at the Git root and set `defaults.run.working-directory: verity-cx` so every quality command executes against the project. Add only the package/tool configuration and documentation needed by Feature 001 and the constitution.

## Phase 0: Research Decisions

Research is consolidated in [research.md](research.md). All planning unknowns are resolved:

1. Use uv's packaged application layout with `uv_build`, a Python 3.12 pin, an empty runtime dependency list, and a locked development group containing pytest, Ruff, mypy, mdformat, and yamlfix.
1. Parse `config/tau3-bench.toml` with `tomllib` into immutable typed configuration objects; production scripts accept no source, revision, destination, or config overrides.
1. Derive the project root from each script's `__file__`, pass it explicitly into library functions, and reject absolute or escaping configured paths.
1. Run every Git process with an argument list, `shell=False`, captured text output, disabled terminal prompting, and optional locks disabled during validation.
1. Validate checkout identity in a fixed order: real directory, standalone worktree root, exact origin, exact `HEAD`, tag-to-commit binding, empty porcelain status, then required banking data.
1. Use a unique current-run-owned staging parent plus a cooperative setup lock; validate fully before same-filesystem promotion and never fetch, reset, repair, replace, or clean a pre-existing target.
1. Parse only the application-safe `db.json` as JSON during validation. Count and prove readability of document and task files without decoding or displaying evaluation tasks.
1. Expose deterministic human-readable CLI summaries with stable error categories and conventional exit codes `0`, `1`, and `2`.
1. Test entirely against temporary local Git repositories and synthetic canary content, including offline idempotency and output non-disclosure.

## Phase 1: Design and Contracts

### Configuration and Pin

`config/tau3-bench.toml` is the only production source of truth. It records schema version, MIT licence identifier, exact HTTPS clone URL, tag, full SHA, final checkout path, and all three required banking-data paths. Paths use project-root-relative forward-slash notation and are validated as descendants of the project root and the configured checkout. See [configuration.md](contracts/configuration.md).

### Reusable Module Responsibilities

`src/veritycx/data_sources/tau3.py` contains four deliberately separated layers:

1. **Typed configuration and path resolution**: Load the fixed TOML file, reject missing/unknown/malformed fields, validate the 40-character lowercase hexadecimal SHA, and resolve paths from the explicit VerityCX project root with containment checks.
1. **Git boundary**: Execute Git with `subprocess.run()` argument lists and no shell; translate missing Git and nonzero exits into typed, sanitized errors; validate origin, revision, tag binding, and cleanliness without optional index locks.
1. **Banking-data boundary**: Verify required path kinds, containment, non-empty recursive file sets, and actual readability without following symbolic links or junctions; decode only `db.json`, require a non-empty top-level object, and derive collection shapes without retaining record values in report objects.
1. **Orchestration and inspection**: Validate an existing target without mutation, create and own staging state for first acquisition, promote only a fully valid checkout, and return narrow immutable setup/inspection summaries.

The module MUST NOT provide a generic upstream file reader. Public results contain identifiers, counts, kinds, and error categories only.

### Setup Workflow

The default setup contract is `uv run python scripts/setup_tau3_data.py`; read-only validation is `uv run python scripts/setup_tau3_data.py --check`. Detailed states and outputs are defined in [setup-cli.md](contracts/setup-cli.md).

1. The script derives the VerityCX project root from `scripts/setup_tau3_data.py`, loads the fixed config, and resolves every configured path from that root rather than from the caller's current directory.
1. Before creating `.cache/`, it classifies `.cache/tau3-bench/` without following links or junctions.
1. If the target exists, it validates the target in place. A valid target exits successfully without acquiring a lock or contacting the remote. Any invalid target produces a precise error and remains unchanged.
1. If `--check` is present and the target is missing, setup returns a missing-checkout error without creating `.cache/`, a lock, or staging state.
1. For first acquisition, setup verifies Git availability, creates `.cache/` only if absent and safe, then atomically claims `.cache/tau3-bench.setup.lock/`. A pre-existing lock is preserved and reported with manual recovery guidance.
1. After taking the lock, setup rechecks that the final target is absent, then creates a unique absolute staging parent using prefix `tau3-bench-staging-` beneath `.cache/`; it clones into the parent's initially nonexistent `checkout/` child.
1. Clone uses the configured URL and tag with a single-branch argument-list invocation. Terminal prompting is disabled, so the public repository cannot unexpectedly request credentials.
1. In the staged checkout, setup requires one exact `origin` URL, verifies `git rev-parse HEAD` equals `fc0055dc4e0a316c3f83133267fbd6faaa770992`, verifies the peeled `v1.0.1` tag resolves to that SHA, and requires empty no-optional-locks porcelain status.
1. Setup validates the three configured banking paths, recursively counts and opens regular document/task files without following links, and parses `db.json` as a non-empty top-level JSON object.
1. Setup repeats the clean check and final-target absence check immediately before promotion, then renames the staged checkout within `.cache/`; it never uses replace semantics.
1. Setup validates the promoted checkout before reporting success. On any failure before promotion, `finally` removes only the exact staging parent and cooperative lock created and recorded by the current invocation. It never searches for or removes other staging directories, stale locks, or the final target.
1. If the destination appears during the controlled setup window, setup preserves it, aborts promotion, removes only its own staging state, and reports the conflict.
1. A handled failure removes only staging and lock paths recorded as owned by the current invocation. State surviving abrupt termination or cleanup failure is unowned by later invocations: a surviving lock blocks setup and is reported with manual recovery guidance, while unrelated stale staging directories remain untouched. The final target is never partially populated.
1. If validation fails after promotion, setup preserves the promoted checkout for manual review, removes only its owned lock and now-empty staging parent, and reports the categorized failure without rollback, repair, or replacement.

### Validation Rules

- Reject the target or `.cache/` when it is an unexpected file, symbolic link, junction, unreadable directory, or path outside the resolved project root.
- Require the Git top level to be the checkout itself so Git cannot walk upward and validate VerityCX by mistake.
- Compare the sole configured `remote.origin.url` byte-for-byte with `https://github.com/sierra-research/tau2-bench.git`; do not accept SSH URLs, mirrors, URL rewrites, or credential-bearing variants.
- Treat the full commit SHA as authoritative while independently requiring `refs/tags/v1.0.1^{commit}` to resolve to it.
- Use `git --no-optional-locks status --porcelain=v1 --untracked-files=all`; do not print porcelain entries or filenames in errors.
- Directory validation rejects links, junctions, special files, unreadable files, escaping descendants, and empty file sets. It counts recursive regular files without printing names.
- Database validation decodes UTF-8 `db.json`, rejects malformed JSON, a non-object root, or an empty object, and reports syntax line/column without echoing source text.
- Git 2.34 or newer and uv 0.12.5 form the supported tool baseline. Commands record versions in CI, treat filenames as opaque, use locale-independent project-owned fields/categories, and fail safely when host path-length or permission rules prevent access.
- Configuration failures, missing tools, credential-bearing or rewritten origins, terminal-prompt attempts, escaping paths, and untrusted filenames terminate at typed boundaries before unsafe state is exposed or promoted.

### Safe Inspection

`uv run python scripts/inspect_tau3_banking_data.py` performs the same non-mutating checkout and banking validation, derives an approved summary, then repeats identity, cleanliness, required-path, count, and database-shape validation before printing. A detected difference fails as `checkout-changed` with no stdout. Successful output contains only the verified tag, exact SHA, recursive document count, recursive task count, and sorted top-level database collection name/kind/direct-count tuples. It never prints nested database keys, database values, document bodies or names, task names or contents, prompts, evaluation criteria, reference actions, grading data, or expected answers. See [inspection-cli.md](contracts/inspection-cli.md) and [data-use-policy.md](contracts/data-use-policy.md).

### Network-Independent Test Strategy

`tests/data_sources/test_tau3.py` uses pytest fixtures and helpers with complete type annotations and docstrings. A fixture creates a temporary source repository, configures local Git identity, writes synthetic required paths, commits them, tags the commit `v1.0.1`, creates a local bare remote, and builds an injected `Tau3Config` from the dynamic URL and SHA. No production constant is patched and no test reaches the internet.

Required coverage:

| Scenario | Test design and proof |
|---|---|
| Successful setup | Clone the valid local remote; assert final target, exact origin/tag/SHA, valid data, and absence of current-run staging. |
| Correct-checkout rerun | Make the local remote unavailable after setup; rerun and assert success, no Git clone call/network dependency, and unchanged checkout-content snapshot. |
| Read-only `--check` | Test valid and missing targets; assert success/failure respectively and identical pre/post filesystem snapshots, including no cache creation for missing target. |
| Incorrect origin | Change `origin`; assert `origin-mismatch`, unchanged target, and no download. |
| Incorrect commit SHA | Use a clean checkout or config with a different valid 40-hex SHA; assert `revision-mismatch` and no promotion/repair. |
| Incorrect tag binding | Point the expected tag at another commit while `HEAD` remains otherwise controlled; assert `tag-mismatch`. |
| Local modifications | Parameterize a tracked edit and untracked file; assert `dirty-checkout` without printing paths and preserve changes. |
| Incomplete banking data | Commit variants with each required path missing, empty, or the wrong kind; assert path-specific failures. |
| Malformed required JSON | Commit invalid `db.json`, plus valid non-object and empty-object variants; assert sanitized database errors without source snippets. |
| Failed staging clone | Use an unavailable local remote; assert `clone-failed`, final target absent, current staging removed, and unrelated pre-existing staging preserved. |
| Abrupt termination recovery | Pre-create a setup lock and related stale staging state representing an interrupted invocation; assert a later run reports the lock, supplies recovery guidance, preserves every byte, and never promotes or removes the stale checkout. |
| Unexpected filesystem targets | Cover regular file and symbolic-link targets everywhere, plus junction behavior where supported; assert rejection without following or changing them. |
| Root independence | Invoke from a different current directory; assert all paths still resolve beneath the explicit temporary project root. |
| Safe inspection output | Place unique canaries in a document body, nested synthetic record, task prompt, expected answer, reference action, and grading criteria; assert none occurs in stdout, stderr, report `repr`, or serialized report while counts/shapes remain correct. |
| Concurrent inspection change | Inject a state/count/shape change between the initial and final validation; assert `checkout-changed`, empty stdout, no traceback, and no filesystem mutation by inspection. |
| Preservation evidence | Snapshot file bytes, links/object identity, exposed permissions, Git references/index/worktree state, and sibling cache entries before every conflict case; exclude access timestamps and inject permission failures when host privileges are nondeterministic. |

Permission failures use injected file operations or monkeypatching to raise `PermissionError`, ensuring deterministic coverage on Windows and POSIX without relying on host privilege behavior.

### Documentation and Attribution

- Project-root `README.md` exposes the single setup command, `--check`, inspection, prerequisites, tests, and the external-cache boundary.
- `docs/data/tau3-banking.md` records source, MIT licence, tag, SHA, every complete relative path, commands, safe inspection fields, application-safe allow-list, evaluation-only deny-list, and out-of-scope future work.
- `THIRD_PARTY_NOTICES.md` attributes Sierra Research, links the upstream repository and MIT licence, and states that upstream files are downloaded locally and never committed.
- Module READMEs satisfy constitution requirements and document interfaces, invariants, failure modes, configuration, and test commands.
- `.gitignore` excludes `.cache/tau3-bench/`, `.cache/tau3-bench-staging-*/`, and `.cache/tau3-bench.setup.lock/` without ignoring unrelated repository content.

## Verification Commands

Run from the VerityCX project root after implementation:

```text
git --version
uv --version
uv lock --check
uv sync --locked
uv run ruff format --check src scripts tests
uv run mdformat --check README.md THIRD_PARTY_NOTICES.md config/README.md docs/data/tau3-banking.md
uv run mdformat --check scripts/README.md src/veritycx/README.md src/veritycx/data_sources/README.md tests/data_sources/README.md
uv run mdformat --check specs/001-acquire-tau3-banking/spec.md specs/001-acquire-tau3-banking/plan.md specs/001-acquire-tau3-banking/research.md specs/001-acquire-tau3-banking/data-model.md specs/001-acquire-tau3-banking/quickstart.md specs/001-acquire-tau3-banking/tasks.md
uv run mdformat --check specs/001-acquire-tau3-banking/contracts/configuration.md specs/001-acquire-tau3-banking/contracts/data-use-policy.md specs/001-acquire-tau3-banking/contracts/inspection-cli.md specs/001-acquire-tau3-banking/contracts/setup-cli.md ../.github/workflows/README.md
uv run yamlfix --check ../.github/workflows/quality.yml
uv run mypy --strict src scripts tests
uv run pytest tests/data_sources/test_tau3.py
uv run ruff check src/veritycx/data_sources/tau3.py scripts/setup_tau3_data.py scripts/inspect_tau3_banking_data.py tests/data_sources/test_tau3.py
uv run python scripts/setup_tau3_data.py --check
uv run python scripts/inspect_tau3_banking_data.py
```

For a new clone, run the documented acquisition command before the final two live-data checks:

```text
uv run python scripts/setup_tau3_data.py
```

The four verification commands supplied in the feature input are preserved verbatim. Lock verification, Python formatting, explicit maintained-Markdown formatting, workflow-YAML formatting, and strict typing are additional constitution gates. The explicit Markdown list prevents recursive formatting of `.agents/`, `.specify/`, generated, vendored, or unrelated files.

The same non-live-data quality commands run in the Git-root `.github/workflows/quality.yml` on all three required operating-system jobs with `verity-cx` as the working directory. The workflow pins uv 0.12.5, requires Git 2.34 or newer, records the runner image and Python/Git/uv versions, and records the first-acquisition duration. CI uses only the temporary local Git fixtures and MUST NOT acquire data from GitHub. Every matrix job is required before merge.

## Post-Design Constitution Check

| Principle | Result after Phase 1 |
|---|---|
| Module documentation | PASS — every new responsibility-bounded package, Git-root CI workflow, project config, script, and test area has an explicit README owner in the structure. |
| File-level and interface documentation | PASS — the design requires module comments/docstrings and documented typed callables in all maintained Python. |
| Strict typing | PASS — typed immutable models, validated external boundaries, and strict mypy cover source, scripts, and tests. |
| Automated quality | PASS — a required three-operating-system CI matrix runs deterministic lock, Python/Markdown/YAML format, lint, type, and network-independent unit/integration gates; check and inspection commands remain documented local verification steps. |
| Scope discipline | PASS — no feature work extends into ingestion, agents, APIs, containers, or evaluation execution. |

**Post-design gate result**: PASS. No constitution violations remain and no Complexity Tracking section is needed.
