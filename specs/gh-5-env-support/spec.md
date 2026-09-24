<!-- Defines requirements and acceptance boundaries for repository-wide dotenv configuration. -->

# Feature Specification: Repository Environment Configuration

**Feature Branch**: `symphony/gh-5-env-support`

**Created**: 2026-09-24

**Status**: Draft

**Input**: Add `.env` support, provide a safe `.env.example`, ensure project-owned environment
configuration can be obtained through `.env`, and enforce that `.env.example` contains every and
only environment-variable name required by the repository.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure a local checkout from one template (Priority: P1)

A developer copies the repository's example environment file to the ignored local environment file,
fills in the values needed for the workflow they intend to run, and can start repository commands
without manually exporting each project setting into the shell.

**Why this priority**: A single discoverable and safe configuration path is the main user value of
the feature.

**Independent Test**: Start a representative runtime or management command in a clean process whose
project-owned settings are supplied only in the repository-root `.env`; the command observes those
settings and retains its existing validation and failure behavior.

**Acceptance Scenarios**:

1. **Given** a fresh checkout and a completed root `.env`, **When** a supported project command starts
   from the repository root, **Then** it obtains the applicable project-owned settings from `.env`
   without requiring manual shell exports.
1. **Given** a setting in both `.env` and the invoking process environment, **When** a supported
   command starts, **Then** the explicitly supplied process value takes precedence so CI and
   one-command overrides remain possible.
1. **Given** no `.env` file, **When** a command that needs configuration starts, **Then** the command
   retains its existing safe missing-configuration outcome rather than crashing, inventing a value,
   or exposing a secret.

______________________________________________________________________

### User Story 2 - Discover the exact configuration contract (Priority: P2)

A contributor can inspect `.env.example` to learn every project-owned environment-variable name
recognized by maintained runtime, management, and validation workflows without finding obsolete,
misspelled, duplicated, or unrelated host-platform variables.

**Why this priority**: The template is useful only if it remains a complete and exact contract with
the code that consumes configuration.

**Independent Test**: Compare the normalized names in `.env.example` with the maintained inventory
of project-owned environment-variable reads; the two sets are identical and every entry has a safe
placeholder or nonsecret example.

**Acceptance Scenarios**:

1. **Given** the current repository, **When** the environment-contract check runs, **Then** every
   project-owned configuration name read by maintained application or project-command code appears
   exactly once in `.env.example`.
1. **Given** an extra, misspelled, duplicated, or missing template name, **When** the check runs,
   **Then** it fails and identifies names by category without printing configured values.
1. **Given** a platform-provided or internally generated variable such as a Git, shell, virtual
   environment, or GitHub Actions control, **When** the template is checked, **Then** that variable is
   not required in `.env.example` unless maintained code explicitly classifies it as project-owned
   configuration.

______________________________________________________________________

### User Story 3 - Prevent configuration drift in normal quality gates (Priority: P3)

A reviewer receives an automated failure when a code change adds, removes, or renames a
project-owned environment-variable dependency without updating the checked-in example contract.

**Why this priority**: Continuous enforcement keeps the template trustworthy after the initial
cleanup.

**Independent Test**: Exercise the contract checker with complete, missing-name, extra-name,
duplicate-name, malformed-line, and secret-canary fixtures, then run it through the repository's
documented local and continuous-integration quality path.

**Acceptance Scenarios**:

1. **Given** source and template names are synchronized, **When** the standard quality checks run,
   **Then** the environment-contract check passes on every supported CI host.
1. **Given** maintained code begins reading a new project-owned setting without a matching example
   entry, **When** the standard quality checks run, **Then** they fail before merge.
1. **Given** a template entry is no longer read as project-owned configuration, **When** the standard
   quality checks run, **Then** they fail until the obsolete entry is removed or its use is restored.

### Edge Cases

- Blank lines and comments in `.env.example` do not count as variable names; whitespace and quoting
  are parsed consistently rather than compared as raw text.
- Duplicate names, malformed assignments, export-prefixed assignments, and names that differ only
  through spelling or case fail with a stable diagnostic and no value disclosure.
- Empty values in `.env` remain empty values; they are not silently replaced by example content or
  defaults unless the existing consumer already defines that behavior.
- Optional integrations may leave their values blank locally, but their recognized names remain in
  `.env.example` so enabling the integration does not introduce an undocumented variable.
- Test fixtures and subprocesses may pass explicit in-memory environments; dotenv loading must not
  make isolated tests depend on a developer's real `.env`.
- `.env` and other local variants remain untracked, while `.env.example` is intentionally tracked and
  contains no usable credential, token, password, or database connection string.
- Operating-system, shell, Git, package-tool, virtual-environment, and CI runner controls are not
  treated as project-owned configuration merely because maintained code forwards or inspects them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide a tracked root `.env.example` and MUST continue to exclude
  the root `.env` and local environment variants from version control.
- **FR-002**: Every maintained runtime, management, and validation entry point that consumes
  project-owned environment configuration MUST make the same-named setting obtainable from the root
  `.env` before validating or using it.
- **FR-003**: A value already supplied by the invoking process MUST take precedence over the same
  name in `.env`; loading MUST NOT overwrite explicit CI, test, or one-command overrides.
- **FR-004**: Absence of `.env` MUST remain supported. Existing required/optional rules, defaults,
  sanitized errors, and command exit behavior MUST remain unchanged after configuration loading.
- **FR-005**: `.env.example` MUST contain each recognized project-owned configuration name exactly
  once and MUST contain no unrecognized or obsolete configuration name.
- **FR-006**: The initial recognized project-owned configuration inventory MUST cover runtime
  database and authentication settings, migration settings, dedicated test database settings,
  validation selection settings, live-provider credentials, and optional trace-export settings
  currently consumed by maintained code.
- **FR-007**: Host- and tool-owned inputs—including operating-system and shell settings, Git safety
  controls, virtual-environment/package-tool controls, and GitHub Actions-provided control paths—MUST
  be excluded from the example contract unless they are deliberately reclassified and documented as
  project-owned configuration.
- **FR-008**: Example values MUST be empty or unmistakably nonsecret placeholders. The repository
  MUST NOT commit a usable credential, token, password, private path, or database connection string.
- **FR-009**: The repository MUST provide an automated, deterministic contract check that detects
  missing, extra, duplicate, malformed, and incorrectly named `.env.example` entries without reading
  or reporting `.env` values.
- **FR-010**: The contract check MUST derive or validate the required-name inventory against
  maintained configuration consumers so adding, removing, or renaming a project-owned environment
  dependency cannot pass solely because a second hand-maintained list was changed incorrectly.
- **FR-011**: The environment-contract check MUST run as part of the repository's documented local
  test path and continuous-integration quality gates on every supported host.
- **FR-012**: Dotenv loading MUST be rooted at the single Git project root and MUST NOT depend on the
  caller's current working directory, a nested project root, or discovery outside the repository.
- **FR-013**: Test and subprocess boundaries that intentionally receive explicit environment
  mappings MUST remain isolated from a developer's ambient `.env` unless the test explicitly opts
  into root dotenv loading.
- **FR-014**: Repository, configuration, scripts, source, tests, and CI documentation affected by the
  new configuration contract MUST describe the root `.env` workflow, precedence, variable ownership,
  validation command, and safe failure modes.

### Key Entities

- **Local environment file**: Ignored root `.env` containing developer-specific values; optional as a
  file, secret-bearing, and never read outside the repository root.
- **Example environment contract**: Tracked root `.env.example` containing the exact set of
  recognized project-owned variable names and only safe placeholder values.
- **Project-owned configuration name**: A stable name intentionally consumed to configure VerityCX
  runtime, management, or validation behavior. At specification time these responsibilities include
  `VERITYCX_DATABASE_URL`, `VERITYCX_AUTH_FILE`, `VERITYCX_MIGRATION_DATABASE_URL`,
  `VERITYCX_TEST_DATABASE_URL`, `VERITYCX_TEST_MIGRATION_DATABASE_URL`,
  `VERITYCX_VALIDATION_PROVIDER`, `VERITYCX_VALIDATION_CORPUS`, `OPENAI_API_KEY`,
  `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`.
- **Externally managed environment name**: A host, shell, Git, dependency tool, test harness, or CI
  control that is inspected or forwarded but is not part of the VerityCX configuration contract.
- **Environment-contract check**: A value-blind comparison between maintained consumers and the
  example contract, producing stable name-only diagnostics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All supported root runtime, management, and validation entry points can obtain 100% of
  their project-owned environment settings from a root `.env`, while explicit process values win in
  100% of precedence cases. [FR-002–FR-004, FR-012]
- **SC-002**: For the current repository, the set of normalized names in `.env.example` equals the
  recognized project-owned configuration set exactly: zero missing, extra, duplicate, malformed, or
  incorrectly cased names. [FR-005–FR-010]
- **SC-003**: Automated fixtures detect 100% of seeded missing-name, extra-name, duplicate-name,
  malformed-assignment, precedence, missing-file, and secret-canary cases without disclosing any
  configured value. [FR-003–FR-009, FR-013]
- **SC-004**: The standard local and CI quality paths execute the environment-contract check on Linux,
  Windows, and macOS, and a deliberate one-name source/template mismatch fails every path. [FR-011]
- **SC-005**: A repository secret scan and review of the change find zero usable credentials or local
  `.env` files in tracked content, while `.env.example` remains tracked. [FR-001, FR-008]
- **SC-006**: All changed modules, files, interfaces, and quality-gate documentation satisfy the
  repository constitution's documentation, strict-typing, formatting, and single-root requirements.
  [FR-012, FR-014]

## Assumptions

- This feature covers VerityCX-owned configuration intentionally consumed by maintained runtime,
  management, and validation code. Arbitrary ambient environment state and infrastructure-provided
  controls are outside the example contract.
- `.env` is a developer convenience and default source, not a replacement for secure CI or deployed
  secret injection; explicit process values therefore retain precedence.
- Optional credentials and trace settings belong in `.env.example` because they are recognized
  configuration even when the default deterministic workflow does not require values for them.
- Tests may use synthetic environment mappings and CI may generate or inject configuration without
  committing a real `.env`; both must validate against the same names and behavior.
- The feature changes configuration acquisition and drift detection only. It does not change provider
  choice, database provisioning, authentication design, credential rotation, or deployment hosting.
- Affected responsibilities are the root developer workflow, runtime configuration loading,
  root-level scripts, tests, ignore rules, and CI quality gates. Planning will identify the smallest
  shared loading boundary and exact files while preserving the single project root.
