<!-- Defines the dependency-ordered implementation tasks for Feature 001. -->

# Tasks: Acquire τ³-Banking Data

**Input**: Design documents from `specs/001-acquire-tau3-banking/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, and `.specify/memory/constitution.md`

**Tests**: Required. The specification and implementation plan require network-independent pytest coverage, subprocess-boundary tests, filesystem snapshots, and non-disclosure canaries. Each user-story phase therefore starts with tests that must fail before its implementation tasks begin.

**Organization**: Tasks are grouped by user story so the verified-acquisition MVP is delivered first and later safety and inspection increments remain independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes different files and has no dependency on another incomplete task in the same phase
- **[Story]**: Maps the task to User Story 1, 2, or 3 from `spec.md`
- Paths are project-root-relative unless a task explicitly identifies a Git-root-relative path. Git-root paths include `.github/workflows/`.

## Global Constraints

- Use Python `>=3.12,<3.13`, uv 0.12.5 with `uv_build`, Git 2.34 or newer, standard-library runtime dependencies only, and development-only pytest, Ruff, mypy, mdformat, and yamlfix configuration in `pyproject.toml`.
- Resolve the project root and all production paths from each script's `__file__`, never the caller's current working directory; production source, revision, destination, and config overrides are forbidden.
- Invoke Git with argument sequences, explicit `shell=False`, captured text, `GIT_TERMINAL_PROMPT=0`, and optional locks disabled during validation.
- Never fetch, reset, repair, delete, move, replace, or clean a pre-existing `.cache/tau3-bench/`; clean up only staging and lock paths proven to be owned by the current invocation.
- Feature 001 outputs, errors, reports, and inspection results must exclude evaluation-only material. Maintained documentation must classify later runtime consumers as default-deny and assign enforcement to the consuming feature.
- Every maintained module needs an accurate `README.md`; every maintained Python file and supported text/config file needs a conventional leading comment or docstring; every callable and model must be strictly typed and documented.
- Feature 001 ends at acquisition, pinning, validation, inspection, and documentation. Do not add chunking, embeddings, database import, agent workflows, web endpoints, containers, or benchmark evaluation.

## Planned File Responsibilities

| Path | Responsibility |
|---|---|
| Git root: `.github/workflows/README.md`, `.github/workflows/quality.yml` | Documented three-operating-system CI module that runs against project root `verity-cx/` |
| `pyproject.toml`, `.python-version`, `uv.lock` | Reproducible Python 3.12 package, development tools, and quality-gate configuration |
| `config/tau3-bench.toml` | Sole production source of truth for the exact upstream pin and required paths |
| `src/veritycx/data_sources/tau3.py` | Typed configuration, path, Git, data-validation, setup-transaction, and inspection logic |
| `scripts/setup_tau3_data.py` | Thin setup and read-only `--check` CLI |
| `scripts/inspect_tau3_banking_data.py` | Thin non-mutating safe-inspection CLI |
| `tests/data_sources/test_tau3.py` | Network-independent local-Git, filesystem, CLI, and non-disclosure coverage |
| `README.md`, module `README.md` files, `docs/data/tau3-banking.md`, `THIRD_PARTY_NOTICES.md` | Commands, contracts, provenance, operating constraints, tests, and data-use policy |
| `.gitignore` | Precise external-cache, setup-lock, and staging-state isolation without ignoring unrelated cache content |

______________________________________________________________________

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the minimal packaged Python project and project-root runtime-state boundaries.

- [x] T001 Create `pyproject.toml` with `uv_build`, Python `>=3.12,<3.13`, no runtime dependencies, a locked development group for pytest/Ruff/mypy/mdformat/yamlfix, strict mypy coverage of `src`, `scripts`, and `tests`, deterministic Ruff/pytest configuration including documentation rules for maintained Python interfaces, deterministic mdformat/yamlfix configuration for the explicit maintained-Markdown set and Git-root workflow YAML, and documented verification compatibility with uv 0.12.5
- [x] T002 [P] Pin Python `3.12` in `.python-version`
- [x] T003 [P] Create documented package markers and explicit exports in `src/veritycx/__init__.py` and `src/veritycx/data_sources/__init__.py`
- [x] T004 [P] Generate and commit the deterministic dependency resolution in `uv.lock` from `pyproject.toml`
- [x] T005 [P] Add precise ignore rules for `.cache/tau3-bench/`, `.cache/tau3-bench-staging-*/`, and `.cache/tau3-bench.setup.lock/` in `.gitignore` without ignoring unrelated cache content

**Checkpoint**: `uv lock --check` can validate the project metadata, package imports resolve under `uv run`, and all generated τ³ runtime state has an explicit version-control boundary.

______________________________________________________________________

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the fixed configuration, typed external-data boundaries, and reusable network-independent test harness that block all user stories.

**⚠️ CRITICAL**: No user-story implementation begins until this phase passes its focused tests.

- [x] T006 [P] Create schema version 1 with the exact MIT licence, canonical repository URL `https://github.com/sierra-research/tau2-bench.git`, `v1.0.1` tag, `fc0055dc4e0a316c3f83133267fbd6faaa770992` SHA, and four project-root-relative paths in `config/tau3-bench.toml`
- [x] T007 [P] Build typed pytest helpers in `tests/data_sources/test_tau3.py` that create temporary working and bare Git repositories, synthesize required banking paths and unique disclosure canaries at runtime, inject `Tau3Config`, capture filesystem byte snapshots, and never access GitHub
- [x] T008 Add failing schema and path-boundary tests in `tests/data_sources/test_tau3.py` for missing/unknown/duplicate/wrong-type TOML fields, boolean schema versions, malformed or non-production pins, absolute/drive/UNC/parent-traversal paths, resolved escapes, checkout-child relationships, and current-directory independence
- [x] T009 Implement frozen, strictly typed `Tau3UpstreamConfig`, `Tau3PathConfig`, `Tau3Config`, `ResolvedTau3Paths`, `Tau3OperationError`, `load_tau3_config()`, and `resolve_tau3_paths()` in `src/veritycx/data_sources/tau3.py` until the T008 tests pass before any Git or cache mutation is possible
- [x] T010 Add failing subprocess and data-boundary tests in `tests/data_sources/test_tau3.py` for argument-list Git execution, Git 2.34 minimum enforcement, prompt/optional-lock environment controls, sanitized nonzero/missing-Git failures, non-following file traversal, link/junction/special-file rejection, unreadable files, UTF-8 JSON errors, and safe top-level collection shapes
- [x] T011 Implement the typed Git runner, non-following filesystem classifier/traverser, minimal task-file readability checks, `db.json` parser, JSON-kind mapper, and sanitized boundary errors in `src/veritycx/data_sources/tau3.py` until the T010 tests pass without retaining record or evaluation values

**Checkpoint**: Configuration and untyped TOML/JSON/subprocess/filesystem inputs enter the application only through documented strict-typing boundaries, and the local-Git test harness is ready for story tests.

______________________________________________________________________

## Phase 3: User Story 1 - Acquire a Verified Dataset (Priority: P1) 🎯 MVP

**Goal**: Give a developer one root-level command that installs the approved τ³-Banking checkout through owned staging and proves its exact provenance and required data before promotion.

**Independent Test**: From a temporary clean VerityCX root with no cache, run the setup CLI against the local bare fixture and verify the final checkout has the exact origin, HEAD, tag binding, clean state, readable non-empty required paths, parsed non-empty database object, no surviving owned staging/lock, no secret requirement, and no tracked upstream content.

### Tests for User Story 1

- [x] T012 [US1] Add failing first-install tests in `tests/data_sources/test_tau3.py` for Git availability, single-branch staged clone, exact origin/HEAD/peeled-tag/cleanliness validation, complete banking-data validation, same-filesystem non-replacing promotion, final revalidation, and cleanup of only current-run-owned state
- [x] T013 [US1] Add failing required-data and root-independence tests in `tests/data_sources/test_tau3.py` covering each missing, empty, wrong-kind, unreadable, linked, junction, special, escaping, malformed-JSON, non-object, and empty-object variant while asserting no document, record, task, or raw Git-status content is disclosed
- [x] T014 [US1] Add failing setup-CLI tests in `tests/data_sources/test_tau3.py` for invocation from another current directory, success code `0`, deterministic `status/mode/checkout/tag/commit` stdout, expected-error code `1` on first-install failure, argparse code `2`, stderr routing, exactly one stable diagnostic category with safe fields/recovery, no partial output or traceback, and no API-key or environment override

### Implementation for User Story 1

- [x] T015 [US1] Implement `GitCheckoutState`, `BankingDataState`, exact standalone-checkout identity validation, clean-status validation, required-path validation, and sanitized deterministic error categories in `src/veritycx/data_sources/tau3.py` to satisfy T012-T013
- [x] T016 [US1] Implement `SetupExecution`, the immutable setup result, cooperative lock acquisition, unique `tau3-bench-staging-` ownership, argument-list clone, staged validation, destination recheck, non-replacing rename promotion, post-promotion validation, and exact-owned-state cleanup in `src/veritycx/data_sources/tau3.py`
- [x] T017 [US1] Implement the project-root-resolving default acquisition command and stable success/error translation in `scripts/setup_tau3_data.py` with no production source, revision, destination, or config options
- [x] T018 [P] [US1] Document prerequisites, the single acquisition command, installed success fields, external-cache boundary, first-install failures, and verification entry points in `README.md`
- [x] T019 [P] [US1] Document the fixed schema, authority, exact pin, path-containment rules, production-override prohibition, and test-injection boundary in `config/README.md`
- [x] T020 [P] [US1] Document the package purpose, public imports, root-resolution invariant, dependency boundary, setup usage, and package-level test command in `src/veritycx/README.md`
- [ ] T021 [US1] Define the SC-007 audit procedure in `specs/001-acquire-tau3-banking/quickstart.md` and execute it: verify `git ls-files -- .cache/tau3-bench/` returns zero paths; verify `git check-ignore -v .cache/tau3-bench/` resolves to the intended `.gitignore` rule; record the baseline and candidate commit SHAs; enumerate the complete tracked change set; confirm every changed path is within the planned file responsibilities; review every non-generated addition for upstream-derived source, data, or evaluation content; and record the reviewed paths, reviewer, date, and explicit pass/fail result without reproducing upstream contents. Record any required ignore-rule correction in `.gitignore`.

**Checkpoint**: User Story 1 is a locally demonstrable MVP: a fresh local fixture installs through staging, the exact approved source and banking paths validate, the public CLI contract passes, and existing upstream bytes never enter version control. Cross-platform acceptance scenario 4 and SC-002 remain pending until T042, T047, and T048 pass on all three required runners; this checkpoint is not Feature 001 release completion.

______________________________________________________________________

## Phase 4: User Story 2 - Re-run Setup Safely (Priority: P2)

**Goal**: Make routine setup reruns fast and offline while every missing, conflicting, unsafe, dirty, or concurrent state fails precisely without altering user-owned content.

**Independent Test**: Snapshot a correct checkout, make its local remote unavailable, run default setup and `--check`, and prove both succeed without clone or byte changes; then snapshot each conflicting target/lock/race state, run setup, and prove the correct category is emitted while every pre-existing byte and unrelated staging directory remains unchanged.

### Tests for User Story 2

- [x] T022 [US2] Add failing offline-idempotency and `--check` tests in `tests/data_sources/test_tau3.py` for valid and invalid existing modes, no clone/remote/network/lock, identical pre/post preservation snapshots, valid check mode, missing-checkout failure, and zero cache/lock/staging/report creation when check mode starts without `.cache/`
- [x] T023 [US2] Add failing preserved-conflict tests in `tests/data_sources/test_tau3.py` for incomplete checkout, non-repository, wrong or multiple origins, wrong SHA, wrong or absent tag binding, tracked edits, and untracked files; assert distinct categories, assert that `origin-mismatch` reports the expected URL and a credential-redacted detected origin, assert that `revision-mismatch` reports the expected and detected full SHAs, and assert no download, secret disclosure, or target mutation
- [x] T024 [US2] Add failing transaction-safety tests in `tests/data_sources/test_tau3.py` for file/link/junction/unreadable target and cache paths, escaping and case-sensitive containment, pre-existing setup lock, two concurrent supported setups, simulated abrupt termination with surviving lock and staging state, failures before/during/after promotion, destination appearance before promotion, cleanup failure, unrelated/stale staging preservation, and deterministic injected permission failures on Windows and POSIX; compare bytes, object/link identity, exposed permissions, Git references/index/worktree state, and sibling cache entries while excluding access timestamps

### Implementation for User Story 2

- [x] T025 [US2] Implement target classification before cache creation, valid-existing fast path, missing-target check mode, no-optional-locks read-only validation, and offline-safe `existing`/`check` results in `src/veritycx/data_sources/tau3.py` until T022 passes
- [x] T026 [US2] Complete precise `configuration-invalid`, `git-unavailable`, `checkout-missing`, `unexpected-target`, `not-standalone-repository`, `origin-mismatch`, `revision-mismatch`, `tag-mismatch`, `dirty-checkout`, `banking-data-invalid`, `malformed-database`, and `checkout-changed` diagnostics in `src/veritycx/data_sources/tau3.py`; emit exactly one category with the configured/owned path, safe expected/detected fields, and non-destructive recovery; report the expected URL and a credential-redacted detected-origin summary for `origin-mismatch`, report the expected and detected full commit SHAs for `revision-mismatch`, and never disclose filenames, porcelain entries, source snippets, credentials, raw commands, or unclassified exception data
- [x] T027 [US2] Harden ownership and race handling for `setup-locked`, `clone-failed`, `destination-conflict`, and `staging-cleanup-failed` in `src/veritycx/data_sources/tau3.py`, preserving every unowned target, lock, staging directory, and local modification while removing only recorded current-run state
- [x] T028 [US2] Add the sole optional `--check` flag, `existing`/`check` success modes, argparse usage behavior, categorized recovery guidance, and no-traceback expected failures in `scripts/setup_tau3_data.py`
- [x] T029 [P] [US2] Document the setup/check mode matrix, validation order, stable outputs, diagnostic recovery, cooperative lock, staging ownership, and non-destructive guarantees in `scripts/README.md`
- [x] T030 [P] [US2] Document typed setup interfaces, configuration/Git/data layers, validation order, transaction state machine, security invariants, and failure modes in `src/veritycx/data_sources/README.md`

**Checkpoint**: User Story 2 passes offline rerun and snapshot tests, `--check` is intentionally non-mutating, and all unsafe or concurrent states remain preserved with actionable sanitized diagnostics.

______________________________________________________________________

## Phase 5: User Story 3 - Inspect and Use Data Responsibly (Priority: P3)

**Goal**: Provide a non-mutating structural inspection command plus complete provenance and allow-list/deny-list documentation without exposing source records or benchmark semantics.

**Independent Test**: Run inspection against the valid local fixture containing unique canaries in document bodies, nested database records, task prompts, expected answers, reference actions, and grading criteria; verify exact counts and sorted top-level collection shapes while every canary is absent from result objects, serialization, stdout, stderr, and expected-error paths, then confirm the maintained documentation identifies every required provenance and data-use boundary.

### Tests for User Story 3

- [x] T031 [US3] Add failing inspection-summary tests in `tests/data_sources/test_tau3.py` for verified tag/SHA, recursive document/task counts, sorted top-level `object/array/string/number/boolean/null` kinds including empty collections, direct counts only for objects/arrays, independently derived expected counts/shapes, immutable safe result representations, and absence of every generated document/database/evaluation canary from all fields, errors, `repr`, and supported serialization
- [x] T032 [US3] Add failing inspection-CLI tests in `tests/data_sources/test_tau3.py` for exact line-oriented stdout, success code `0`, usage code `2`, validation error code `1`, `checkout-changed` on an injected state/count/shape change between initial and final validation, no partial summary or traceback on failure, malformed-database line/column sanitization, and identical preservation snapshots proving no clone/fetch/repair/lock/staging/cache/report mutation

### Implementation for User Story 3

- [x] T033 [US3] Implement immutable `DatabaseCollectionShape` and `InspectionSummary`, safe shape derivation, buffered initial and final identity/cleanliness/path/count/shape validation, `checkout-changed` comparison, `inspect_tau3_data()`, and deterministic summary formatting in `src/veritycx/data_sources/tau3.py` without retaining nested keys, scalar values, filenames, record identifiers, task semantics, or raw source representations
- [x] T034 [US3] Implement the no-option, project-root-resolving, validation-first inspection command with stable stdout/stderr and exit-code translation in `scripts/inspect_tau3_banking_data.py`
- [x] T035 [P] [US3] Document source, exact pin, all complete paths, setup/check/inspection commands, safe output fields, application-safe allow-list, evaluation-only deny-list, recovery rules, verification commands, and explicit Feature 001 exclusions in `docs/data/tau3-banking.md`
- [x] T036 [P] [US3] Attribute Sierra Research, the official repository, MIT licence, `v1.0.1`, exact SHA, local-download behavior, and untracked external-file boundary in `THIRD_PARTY_NOTICES.md`
- [x] T037 [P] [US3] Add the inspection command, safe output contract, third-party documentation link, allow-list/deny-list summary, and explicit exclusions to `README.md`
- [x] T038 [P] [US3] Add inspection usage, output restrictions, exit behavior, and validation-first/no-mutation guarantees to `scripts/README.md`
- [x] T039 [P] [US3] Document local-Git fixtures, generated canaries, platform permission injection, test commands, and forbidden real-network/upstream-content use in `tests/data_sources/README.md`
- [x] T040 [P] [US3] Add inspection interfaces, safe result fields, serialization restrictions, default-deny policy, and non-disclosure failure modes to `src/veritycx/data_sources/README.md`

**Checkpoint**: User Story 3 reports only approved structural metadata, all canary channels remain clean, inspection is non-mutating, and documentation alone answers provenance, usage, and evaluation-isolation questions.

______________________________________________________________________

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Apply constitutional documentation and strict-quality gates across the complete feature without expanding its scope.

- [x] T041 Audit and complete every Constitution-required documentation and typing obligation across Feature 001: verify that `README.md`, `config/README.md`, `scripts/README.md`, `src/veritycx/README.md`, `src/veritycx/data_sources/README.md`, and `tests/data_sources/README.md` each state the module's purpose, responsibilities, boundaries, directory structure, public interfaces, dependencies, configuration, usage, test instructions, operational constraints, and failure modes where applicable; complete module and callable docstrings, explicit types, rationale comments, and public exports in `src/veritycx/__init__.py`, `src/veritycx/data_sources/__init__.py`, `src/veritycx/data_sources/tau3.py`, `scripts/setup_tau3_data.py`, `scripts/inspect_tau3_banking_data.py`, and `tests/data_sources/test_tau3.py`; add conventional leading comments to the maintained supported files listed by this feature; and preserve the `.python-version` and `uv.lock` exemptions. The Git-root `.github/workflows/README.md` remains owned by T047.
- [x] T042 Add cross-platform parameterization for the required `ubuntu-latest`, `windows-latest`, and `macos-latest` Python 3.12 matrix, including Git 2.34-or-newer and uv 0.12.5 prerequisite checks, capability-aware handling of Windows junctions/reparse points, POSIX links, injected permission failures, case behavior, path syntax/length failures, UTF-8 and locale independence, and opaque untrusted filenames in `tests/data_sources/test_tau3.py` without weakening a shared safety assertion in `src/veritycx/data_sources/tau3.py`
- [x] T043 Run `uv lock --check` and `uv sync --locked` against `pyproject.toml` and `uv.lock`, correcting only deterministic project or lock metadata defects in those files
- [x] T044 Run `uv run ruff format --check src scripts tests` and the focused `uv run ruff check` command from `quickstart.md`, correcting formatting, documentation, and lint defects in `src/veritycx/data_sources/tau3.py`, both files under `scripts/`, and `tests/data_sources/test_tau3.py`
- [x] T045 Run `uv run mypy --strict src scripts tests` and correct every type error without `Any`, unchecked casts, ignored diagnostics, or untyped public boundaries in `src/veritycx/`, `scripts/`, and `tests/data_sources/`
- [x] T046 Run `uv run pytest tests/data_sources/test_tau3.py` and close every required acquisition, rerun, conflict, cleanup, inspection, platform, snapshot, and non-disclosure coverage gap in `tests/data_sources/test_tau3.py` and its owned implementation files
- [x] T047 Create the Git-root `.github/workflows/README.md` and `.github/workflows/quality.yml` with conventional leading comments; document the CI module's purpose, responsibilities, boundaries, directory structure, public status-check contract, dependencies, configuration, usage, tests, platform coverage, operational constraints, and failure modes; set `defaults.run.working-directory: verity-cx`; and define required `ubuntu-latest`, `windows-latest`, and `macos-latest` Python 3.12 jobs that pin uv 0.12.5, require Git 2.34 or newer, record the runner image and Python/Git/uv versions plus first-acquisition duration, use locked dependencies, and run `uv lock --check`, `uv sync --locked`, Ruff format and lint checks, the explicit mdformat checks, `yamlfix --check ../.github/workflows/quality.yml`, `mypy --strict`, and the network-independent pytest suite without acquiring the live upstream repository
- [ ] T048 Execute the complete workflow in `specs/001-acquire-tau3-banking/quickstart.md` after T047, including every local and CI-configuration quality gate, one required clean-job attempt of the three-operating-system network-independent first-acquisition verification and under-10-minute measurement with retained runner/tool/version/command/result evidence, a one-environment official-upstream smoke acquisition with independent safe count/shape comparison, recorded but non-normative existing/check/inspection durations, offline valid and invalid reruns, `scripts/setup_tau3_data.py --check`, `scripts/inspect_tau3_banking_data.py`, a repeat of the documented SC-007 audit against the final candidate, including its required evidence record, and a documentation-only SC-008 review, then correct only discrepancies in files owned by Feature 001

**Checkpoint**: All constitution gates, focused tests, documented CLI contracts, and the quickstart pass without exceptions or scope expansion.

______________________________________________________________________

## Requirements Traceability

| Scope | Requirements covered | Primary tasks |
|---|---|---|
| Shared configuration, portability, tracking, and strict quality | FR-002-FR-005, FR-015-FR-016, FR-022; SC-002, SC-007 | T001-T011, T021, T041-T048 |
| User Story 1: verified acquisition | FR-001-FR-008, FR-011; SC-001, SC-005 | T012-T021, T047-T048 |
| User Story 2: safe rerun and check | FR-009-FR-011; SC-003-SC-005 | T022-T030 |
| User Story 3: inspection, provenance, and data use | FR-012-FR-021; SC-006, SC-008 | T031-T040 |

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 — Setup**: No dependencies; T002-T005 may start after T001 establishes `pyproject.toml` where applicable.
- **Phase 2 — Foundational**: Depends on Phase 1. T006 and T007 can begin together; each failing-test task precedes its corresponding `src/veritycx/data_sources/tau3.py` implementation task.
- **Phase 3 — User Story 1**: Depends on Phase 2 and delivers the MVP plus the shared validated-checkout behavior.
- **Phase 4 — User Story 2**: Depends on User Story 1's setup/validation baseline, but remains independently testable through offline and preserved-state scenarios.
- **Phase 5 — User Story 3**: Depends on User Story 1's validation baseline, not on User Story 2; it may proceed in parallel with User Story 2 after User Story 1 completes.
- **Phase 6 — Polish**: Depends on every user story selected for delivery; the full release gate uses all three stories. T047 creates the Git-root CI module after local commands are established, and terminal verification task T048 depends on T041-T047.

### User Story Dependency Graph

```text
Setup → Foundational → US1 (MVP) ─┬→ US2
                                  └→ US3
US2 + US3 → Polish
```

### Within Each User Story

- Write the listed story tests first and run them to confirm they fail for the missing behavior.
- Implement typed reusable behavior in `src/veritycx/data_sources/tau3.py` before the thin CLI layer.
- Run the story's focused tests until they pass before writing or updating its documentation.
- Complete the story checkpoint before starting a dependent story.

## Parallel Opportunities

- Setup tasks T002-T005 change distinct files after T001 and can run concurrently.
- Foundational tasks T006 and T007 change the fixed configuration and test harness independently.
- After T017 passes, US1 documentation tasks T018-T020 can run concurrently; T021 remains the final tracking audit.
- After T028 passes, US2 documentation tasks T029-T030 can run concurrently.
- After T034 passes, US3 documentation tasks T035-T040 can run concurrently because each owns a different file at that point.
- After US1 completes, US2 and US3 can be implemented by separate workers if edits to shared `src/veritycx/data_sources/tau3.py` and `tests/data_sources/test_tau3.py` are coordinated or serialized.

## Parallel Example: User Story 1

```text
Task T018: Document acquisition and verification in README.md
Task T019: Document the fixed pin contract in config/README.md
Task T020: Document package interfaces in src/veritycx/README.md
```

## Parallel Example: User Story 2

```text
Task T029: Document setup/check operations in scripts/README.md
Task T030: Document validation and transaction interfaces in src/veritycx/data_sources/README.md
```

## Parallel Example: User Story 3

```text
Task T035: Write docs/data/tau3-banking.md
Task T036: Write THIRD_PARTY_NOTICES.md
Task T037: Extend README.md
Task T038: Extend scripts/README.md
Task T039: Write tests/data_sources/README.md
Task T040: Extend src/veritycx/data_sources/README.md
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
1. Complete Phase 2: Foundational.
1. Complete Phase 3: User Story 1.
1. Run the US1 focused tests plus its acquisition and version-control-isolation checks on the current development environment.
1. Demonstrate the verified local-fixture acquisition workflow as a provisional MVP before adding rerun or inspection behavior.
1. Do not mark User Story 1 release-complete until T042, T047, and T048 pass on all three required operating-system runners.

### Incremental Delivery

1. Deliver Setup + Foundational as the reproducible, typed project baseline.
1. Deliver US1 as the verified-acquisition MVP.
1. Deliver US2 as the offline, non-destructive rerun/check increment.
1. Deliver US3 as the safe-inspection, provenance, and responsible-data-use increment.
1. Run Phase 6 only for the stories included in the release, with all three required for Feature 001 completion.

### Suggested Commit Boundaries

1. Project setup and fixed configuration: T001-T011.
1. Verified acquisition MVP: T012-T021.
1. Safe rerun and check behavior: T022-T030.
1. Safe inspection and data-use documentation: T031-T040.
1. Cross-cutting quality corrections and required CI: T041-T048.

## Notes

- `[P]` denotes tasks that can run concurrently without writing the same file.
- `[US1]`, `[US2]`, and `[US3]` provide direct traceability to `spec.md`.
- Unqualified paths are relative to project root `verity-cx/`; `.github/workflows/` is relative to the outer Git root.
- Test tasks precede implementation because the feature explicitly requires the network-independent test strategy.
- The local-Git fixtures use synthetic runtime-generated content; no official τ³ data or evaluation task content is committed.
- Stop at any checkpoint to validate the current increment independently.
