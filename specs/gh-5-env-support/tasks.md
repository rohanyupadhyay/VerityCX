______________________________________________________________________

## description: "Implementation tasks for repository-wide dotenv support and contract enforcement"

# Tasks: Repository Environment Configuration

**Input**: Design documents from `specs/gh-5-env-support/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/environment.md`,
and `quickstart.md`

**Tests**: Tests are required by the specification for dotenv acquisition, exact inventory drift,
secret-safe diagnostics, and supported-host quality enforcement. Write each test task before its
paired implementation task and observe the focused failure first.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated as
an independently useful increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes different files and has no incomplete dependency.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task names the exact repository path it changes.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the dependency, ignore rules, and documented test-module boundaries shared by
all stories.

- [ ] T001 Add the pinned `python-dotenv==1.2.3` runtime dependency and refresh the reproducible lock in `pyproject.toml` and `uv.lock`
- [ ] T002 Correct dotenv ignore rules so `.env` and local variants remain ignored while `.env.example` is trackable in `.gitignore`
- [ ] T003 [P] Document the new environment unit and contract test modules, including purpose, configuration, failure modes, and focused commands, in `tests/unit/README.md` and `tests/contract/README.md`

______________________________________________________________________

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared root and test setup required before story-specific tests and code.

**⚠️ CRITICAL**: No user story implementation begins until this phase is complete.

- [ ] T004 Establish the single-root path invariant and documented public environment module boundary in `src/veritycx/README.md` and `src/veritycx/__init__.py`
- [ ] T005 Add an explicit pytest-session dotenv opt-in boundary that can be disabled by isolated tests in `tests/conftest.py`

**Checkpoint**: The dependency, root boundary, and test opt-in point are ready for story work.

______________________________________________________________________

## Phase 3: User Story 1 - Configure a local checkout from one template (Priority: P1) 🎯 MVP

**Goal**: Supported processes obtain project-owned settings from the absolute root `.env` without
overwriting explicit process values or changing established missing-configuration behavior.

**Independent Test**: Run `uv run pytest tests/unit/test_environment.py` and representative service,
worker, management, and validation subprocess tests with a synthetic root `.env`, explicit process
overrides, no `.env`, and a non-root current working directory.

### Tests for User Story 1

- [ ] T006 [P] [US1] Add failing unit coverage for absolute-root loading, `override=False` precedence, empty values, missing files, parse failures, repeated calls, and value-safe diagnostics in `tests/unit/test_environment.py`
- [ ] T007 [P] [US1] Add failing entry-point coverage proving service and worker startup load before configuration reads while explicit mapping APIs remain isolated in `tests/support/contract/test_configuration_loading.py`
- [ ] T008 [P] [US1] Add failing entry-point coverage proving management and validation commands load from root under a non-root current working directory and preserve existing exit categories in `tests/support/contract/test_environment_commands.py`

### Implementation for User Story 1

- [ ] T009 [US1] Implement the typed, documented `load_project_environment()` API using the absolute Git-root `.env`, non-overwriting loading, missing-file no-op behavior, and secret-safe failures in `src/veritycx/environment.py`
- [ ] T010 [US1] Invoke root dotenv loading before the first configuration read in service and worker startup without changing explicit mapping interfaces in `src/veritycx/service/main.py` and `src/veritycx/orchestration/worker.py`
- [ ] T011 [US1] Invoke root dotenv loading before configuration reads in maintained management and validation command entry points in `scripts/manage_support.py` and `scripts/validate_support.py`
- [ ] T012 [US1] Complete and run the focused US1 tests, correcting loader or entry-point behavior while preserving all existing configuration validation in `tests/unit/test_environment.py`, `tests/support/contract/test_configuration_loading.py`, and `tests/support/contract/test_environment_commands.py`

**Checkpoint**: User Story 1 is independently usable with `.env`, explicit overrides, or no file.

______________________________________________________________________

## Phase 4: User Story 2 - Discover the exact configuration contract (Priority: P2)

**Goal**: `.env.example` is a tracked, safe, exact-name contract derived from maintained environment
consumers and rejects drift without reading or printing values.

**Independent Test**: Run `uv run pytest tests/contract/test_environment_contract.py` and
`uv run python scripts/check_environment_contract.py`; exact input passes, and seeded missing,
extra, duplicate, malformed, wrong-case, export-prefixed, unsafe-value, dynamic-read, and secret
canary cases fail with sorted name-only diagnostics.

### Tests for User Story 2

- [ ] T013 [US2] Add failing parser and exact-set tests for blank/comment lines, missing, extra, duplicate, malformed, wrong-case, and export-prefixed entries in `tests/contract/test_environment_contract.py`
- [ ] T014 [US2] Add failing ownership and AST evidence tests for `VERITYCX_*`, adopted provider keys, external host/tool controls, literal read forms, aliases, and fail-closed dynamic project reads in `tests/contract/test_environment_contract.py`
- [ ] T015 [US2] Add failing secrecy tests for unsafe placeholders, absent `.env.example`, seeded secret canaries, value-blind output, stable sorting, and the live repository inventory in `tests/contract/test_environment_contract.py`

### Implementation for User Story 2

- [ ] T016 [US2] Create the tracked root template containing exactly the ten specified project-owned names once with empty or unmistakably nonsecret placeholders in `.env.example`
- [ ] T017 [US2] Implement typed AST environment-read evidence collection and the documented project/external ownership policy in `scripts/check_environment_contract.py`
- [ ] T018 [US2] Implement strict `.env.example` lexical parsing, exact-set comparison, safe-placeholder enforcement, deterministic exit codes, and sorted name-only diagnostics without opening `.env` in `scripts/check_environment_contract.py`
- [ ] T019 [US2] Complete and run the focused US2 tests and the real-repository checker, correcting inventory or diagnostics until all contract cases pass in `tests/contract/test_environment_contract.py`, `scripts/check_environment_contract.py`, and `.env.example`

**Checkpoint**: User Story 2 independently exposes and validates the exact safe configuration contract.

______________________________________________________________________

## Phase 5: User Story 3 - Prevent configuration drift in normal quality gates (Priority: P3)

**Goal**: The contract checker runs through documented local checks and the Linux, Windows, and
macOS CI matrix so environment dependency drift fails before merge.

**Independent Test**: Run the documented local contract command and inspect the quality workflow to
confirm the identical command executes after locked synchronization for all three matrix runners;
seeded source/template drift must make the gate fail.

### Tests for User Story 3

- [ ] T020 [P] [US3] Add repository quality-contract assertions for the documented root command, workflow invocation, three-host matrix coverage, and tracked/ignored dotenv files in `tests/test_repository_layout.py`

### Implementation for User Story 3

- [ ] T021 [US3] Add the environment-contract command to the existing three-host quality job and include all GH-5 Markdown artifacts in deterministic documentation checks in `.github/workflows/quality.yml`
- [ ] T022 [US3] Document the local checker, CI enforcement, supported-host behavior, and value-blind failure output in `.github/workflows/README.md`
- [ ] T023 [US3] Complete and run the focused repository quality-contract test and checker command in `tests/test_repository_layout.py` and `scripts/check_environment_contract.py`

**Checkpoint**: All three stories are independently testable and contract drift is merge-blocking.

______________________________________________________________________

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Keep module documentation, contributor guidance, and repository-wide quality evidence
consistent with the implemented contract.

- [ ] T024 [P] Document root `.env` setup, process precedence, the exact ownership boundary, safe placeholders, checker usage, and failure recovery in `README.md`
- [ ] T025 [P] Document loader, startup integration, and checker responsibilities, configuration names, public interfaces, dependencies, and failure modes in `src/veritycx/README.md`, `src/veritycx/service/README.md`, `src/veritycx/orchestration/README.md`, `scripts/README.md`, and `tests/README.md`
- [ ] T026 Review all changed Python modules for file documentation, function documentation, explicit strict types, validated untyped boundaries, and rationale comments in `src/veritycx/environment.py`, `scripts/check_environment_contract.py`, and changed entry points/tests
- [ ] T027 Run the focused scenarios in `specs/gh-5-env-support/quickstart.md`, then run formatting, lint, strict typing, non-live tests, Markdown, YAML, and `git diff --check` gates from the Git root
- [ ] T028 Review tracked dotenv files and the full diff for credentials, tokens, passwords, private paths, connection strings, generated files, unrelated changes, and incomplete task markers using `.env.example`, `.gitignore`, and `specs/gh-5-env-support/tasks.md`

______________________________________________________________________

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on T001–T003 and blocks all stories.
- **User Story 1 (Phase 3)**: Depends on the foundation; it is the MVP acquisition path.
- **User Story 2 (Phase 4)**: Depends on the foundation and source entry-point inventory established
  by US1; tests T013–T015 precede implementation T016–T018.
- **User Story 3 (Phase 5)**: Depends on the working US2 checker; T020 precedes T021–T023.
- **Polish (Phase 6)**: Depends on all selected stories.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on another story after Phase 2.
- **User Story 2 (P2)**: Uses maintained consumers, including US1 entry-point changes, as inventory
  evidence but is independently validated by its checker and tests.
- **User Story 3 (P3)**: Requires the US2 checker command and remains independently testable through
  repository/workflow assertions.

### Within Each User Story

- Write and observe focused failing tests before implementation.
- Implement the smallest behavior needed for the story.
- Run the story's focused suite before moving to the next priority.
- Files shared by tasks are edited sequentially in task order.

### Parallel Opportunities

- T003 can proceed independently of dependency and ignore-rule setup.
- T006, T007, and T008 cover different test files and can be drafted in parallel.
- T013–T015 are sequential because they share the contract test file.
- T020 can be drafted while US2 documentation is finalized, but it cannot pass before the checker
  exists.
- T024 and T025 change separate documentation surfaces and can run in parallel.

______________________________________________________________________

## Parallel Example: User Story 1

```text
Task T006: Add loader unit coverage in tests/unit/test_environment.py
Task T007: Add service/worker entry-point coverage in tests/support/contract/test_configuration_loading.py
Task T008: Add management/validation command coverage in tests/support/contract/test_environment_commands.py
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
1. Write the US1 tests and observe focused failures.
1. Implement the shared loader and explicit startup calls.
1. Run the US1 focused suite and stop for independent validation.

### Incremental Delivery

1. US1 delivers safe root dotenv acquisition.
1. US2 adds the exact tracked contract and deterministic drift checker.
1. US3 makes drift enforcement part of normal local and CI quality paths.
1. Polish synchronizes documentation and proves every root quality gate.

## Notes

- `[P]` means different files or separable drafting work; tasks sharing a file remain sequential when
  applying changes.
- Custom checklist markers are reviewer-owned and are not implementation task state.
- Mark a task `[X]` only after its changes and focused validation are complete.
- Commit after coherent task groups, not after partially passing work.
