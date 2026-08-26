<!-- Defines the user-visible and governance requirements for Feature 001. -->
# Feature Specification: Acquire τ³-Banking Data

**Feature Branch**: `main`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Create Feature 001 for reproducible acquisition, validation, inspection, and documentation of the external τ³-Banking data dependency."

## Root Definitions

- **Git root**: The outer `VerityCX/` directory containing `.git`.
- **Project root**: The nested `VerityCX/verity-cx/` directory containing
  `pyproject.toml`, `src/`, `scripts/`, `config/`, `specs/`, and `.cache/`.
- Developer commands run from the project root. Production paths, including
  `.cache/tau3-bench/`, resolve relative to the project root from each script's
  location. Repository infrastructure such as `.github/workflows/` is relative
  to the Git root.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Acquire a Verified Dataset (Priority: P1)

As a VerityCX developer, I want one documented command that I can run from the project root so that I obtain the approved τ³-Banking data at the expected local cache path and know that it is the exact version the project supports.

**Why this priority**: Every later feature that uses τ³-Banking depends on developers starting from the same authentic and complete upstream data.

**Automated Independent Test**: On each supported operating system, exercise the setup workflow against a temporary local bare Git remote containing synthetic banking fixtures and verify validated promotion, required paths, stable command behavior, and absence of credential prompts.

**Manual Live Smoke Test**: Before release, run the documented setup command from one clean developer clone against the fixed official upstream pin and verify the installed origin, tag, commit SHA, and required banking paths.

**Acceptance Scenarios**:

1. **Given** a clean clone and network access, **When** a developer runs the documented setup command from the project root, **Then** the official τ³ repository is acquired at `.cache/tau3-bench/` at tag `v1.0.1` and commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`.
2. **Given** the approved checkout is present, **When** setup validates it, **Then** the documents directory, synthetic database file, and tasks directory are all confirmed present, non-empty where applicable, and readable.
3. **Given** setup has completed, **When** repository tracking is inspected, **Then** `.cache/tau3-bench/` and all content below it are excluded from version control and no upstream source or data has been copied into a tracked VerityCX location.
4. **Given** a required Windows, Linux, or macOS verification runner and a synthetic local-Git fixture, **When** the same setup workflow and command contract are exercised, **Then** they complete without operating-system-specific manual data handling.

---

### User Story 2 - Re-run Setup Safely (Priority: P2)

As a developer with an existing cache, I want setup to distinguish a valid cache from an unsafe or incorrect one so that routine re-runs are fast and my local files are never silently replaced.

**Why this priority**: Reproducibility requires both idempotent success for the correct revision and non-destructive failure for every conflicting state.

**Independent Test**: Re-run setup against a correct checkout while offline, then test separate caches containing an incomplete checkout, a different remote, a different revision, and local changes; confirm only the correct checkout succeeds and every conflicting cache remains byte-for-byte unchanged.

**Acceptance Scenarios**:

1. **Given** a complete, clean checkout with the approved upstream and revision, **When** setup is run again, **Then** it succeeds without downloading the repository again or changing the checkout.
2. **Given** `.cache/tau3-bench/` exists but is incomplete, **When** setup is run, **Then** it fails with a message that identifies the missing or unreadable requirement and leaves the existing directory unchanged.
3. **Given** the cache points to a repository other than `https://github.com/sierra-research/tau2-bench.git`, **When** setup is run, **Then** it fails with a message that reports the expected and detected upstream and leaves the existing directory unchanged.
4. **Given** the cache is at any revision other than the approved commit, **When** setup is run, **Then** it fails with a message that reports the expected and detected revisions and leaves the existing directory unchanged.
5. **Given** the cache contains local modifications or untracked content, **When** setup is run, **Then** it reports that the checkout is not clean and does not delete, reset, overwrite, or otherwise alter that content.

---

### User Story 3 - Inspect and Use Data Responsibly (Priority: P3)

As a developer, I want a safe inspection command and clear third-party documentation so that I can confirm what was acquired and understand which portions may be consumed by VerityCX without exposing evaluation answers to the runtime agent.

**Why this priority**: Developers need a useful verification summary, while strict separation of application data from evaluation-only material protects benchmark validity.

**Independent Test**: Run the documented inspection command against the approved checkout and review the attribution and data-use documentation; verify that the summary contains counts and database shape only, and that the documented allow-list and deny-list are unambiguous.

**Acceptance Scenarios**:

1. **Given** a valid checkout, **When** a developer runs the inspection command from the project root, **Then** it reports the document count, task count, and high-level synthetic database structure without displaying document bodies, customer record values, task contents, evaluation criteria, expected answers, or golden actions.
2. **Given** a later application feature needs τ³-Banking data, **When** its permitted inputs are reviewed, **Then** only `documents/` may be used for knowledge retrieval or prompts and `db.json` may be used as synthetic banking state.
3. **Given** any runtime-agent or indexing boundary, **When** τ³ content is selected, **Then** `tasks/`, `tasks.json`, `tasks_voice.json`, evaluation prompts, evaluation criteria, expected answers, golden actions, and other evaluation artifacts are excluded.
4. **Given** a developer reviews third-party attribution, **When** they look for dependency provenance, **Then** they can find the upstream owner and URL, MIT licence, release tag, exact commit SHA, local cache location, and data-use restrictions in one maintained location.

### Edge Cases

- A handled first-acquisition failure before promotion removes only the staging parent and setup lock created by that invocation and leaves the final target absent. If abrupt termination or cleanup failure leaves staging or lock state behind, later runs preserve it. A surviving lock blocks setup with its exact location and manual recovery guidance; unrelated stale staging directories are never removed automatically. A partial checkout is never written to or promoted as `.cache/tau3-bench/`.
- The cache path exists as an empty directory, regular file, symbolic link, junction, non-repository directory, or unreadable directory. Setup fails safely without following, replacing, or deleting unexpected content.
- The expected tag resolves to a commit other than the recorded SHA. Setup treats the immutable commit SHA as authoritative, reports the tag mismatch, and does not accept or overwrite the checkout.
- The checkout has the correct revision but a required path is missing, empty, the wrong kind, or unreadable. Setup reports the affected path and fails validation.
- The synthetic database is readable as a file but cannot be structurally inspected. Inspection fails clearly without dumping its contents.
- Task filenames or counts change because a user modified the cache. The dirty-checkout validation prevents the modified cache from being reported as the reproducible source.
- Setup or inspection is run from outside the project root. The command either locates the VerityCX project root safely or reports the required working location without writing to an unintended path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide exactly one documented setup command, runnable from the VerityCX project root (`verity-cx/`), that acquires and validates the approved external dependency.
- **FR-002**: Setup MUST use the official upstream repository `https://github.com/sierra-research/tau2-bench.git` and store its checkout only at `.cache/tau3-bench/` relative to the project root.
- **FR-003**: The approved source pin MUST be recorded as MIT-licensed release tag `v1.0.1` at exact commit SHA `fc0055dc4e0a316c3f83133267fbd6faaa770992`; both tag and SHA MUST be verified for an acquired checkout.
- **FR-004**: `.cache/tau3-bench/` and all of its descendants MUST be excluded from version control.
- **FR-005**: No τ³ source code, banking documents, synthetic banking data, evaluation tasks, or other acquired upstream content MAY be manually copied into or committed to a tracked VerityCX location.
- **FR-006**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/` exists as a readable, non-empty directory containing readable files.
- **FR-007**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json` exists as a readable file.
- **FR-008**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/` exists as a readable, non-empty directory containing readable files, without displaying or forwarding task contents.
- **FR-009**: Re-running setup with a complete, clean checkout at the approved upstream and revision MUST succeed without downloading the repository again or modifying the checkout.
- **FR-010**: If the target path contains an incomplete checkout, unexpected content, an incorrect upstream, an incorrect revision, or local changes, setup MUST fail with a clear diagnostic and MUST NOT delete, reset, overwrite, move, or modify the existing content.
- **FR-011**: Setup MUST return an unambiguous success or failure result suitable for both a developer and an automated verification check.
- **FR-012**: The project MUST provide one documented inspection command, runnable from the project root, that operates only on an already acquired checkout and does not download or repair data.
- **FR-013**: Inspection MUST report the recursive readable-file count under `documents/`, the recursive readable-file count under `tasks/`, and the synthetic database's top-level collection names, value kinds, and record counts where a count is meaningful.
- **FR-014**: Inspection MUST NOT print document bodies, synthetic customer record values, task contents, task instructions, evaluation criteria, expected answers, or golden actions.
- **FR-015**: Setup and inspection MUST work on supported Windows, Linux, and macOS development environments using the same documented command contract.
- **FR-016**: Setup and inspection MUST require no API keys, credentials, or access to paid services; unauthenticated read access to the public upstream repository is sufficient for first acquisition.
- **FR-017**: Maintained third-party attribution MUST identify Sierra Research, the official upstream URL, the MIT licence, release tag `v1.0.1`, exact commit SHA `fc0055dc4e0a316c3f83133267fbd6faaa770992`, and the fact that acquired files remain external and untracked.
- **FR-018**: Maintained data-use documentation MUST define an allow-list: only banking knowledge files under `documents/` may be indexed, retrieved, or added to runtime prompts by later features, and only `db.json` may be used as later synthetic banking state.
- **FR-019**: Maintained data-use documentation MUST classify `tasks/`, `tasks.json`, `tasks_voice.json`, task instructions, evaluation criteria, expected answers, golden actions, evaluation prompts, and equivalent evaluation artifacts as evaluation-only.
- **FR-020**: Inspection output MUST exclude all evaluation-only material. Maintained data-use documentation MUST define runtime agents, prompt builders, knowledge indexes, and application-facing data loaders as default-deny consumers and MUST state that later features are responsible for enforcing FR-018 and FR-019 before consuming upstream data.
- **FR-021**: All other upstream files, including upstream source code and prompts not expressly allow-listed by FR-018, MUST remain an external acquisition dependency and MUST NOT be treated as VerityCX application data.
- **FR-022**: This feature MUST stop at acquisition, pinning, validation, inspection, and documentation; it MUST NOT add document chunking, embeddings, database import, agent workflows, web endpoints, container infrastructure, or benchmark evaluation.

### Key Entities

- **Upstream Source Pin**: The immutable identity of the external dependency, consisting of owner, repository URL, licence, release tag, and exact commit SHA.
- **Cached Checkout**: The untracked local repository at `.cache/tau3-bench/`, including its upstream identity, checked-out revision, cleanliness, and required-path validation state.
- **Banking Knowledge Dataset**: The acquired banking domain content partitioned into runtime-eligible knowledge documents, runtime-eligible synthetic database state, and evaluation-only tasks and evaluation artifacts.
- **Inspection Summary**: A non-sensitive report containing document and task file counts plus collection-level database shape, without source record or evaluation content.
- **Data-Use Classification**: The maintained allow-list and deny-list governing whether an upstream path may be indexed, placed in prompts, loaded as synthetic application state, or reserved exclusively for evaluation.

### Affected Modules and Public Contracts

- **Developer data acquisition module**: Owns the setup and validation behavior for the external cache and requires a module README covering purpose, dependencies, usage, tests, constraints, and failure modes.
- **Developer inspection module**: Owns the safe structural summary behavior and requires documentation of precisely what it reads and what it is forbidden to reveal.
- **Continuous-integration quality module**: Owns the required Python 3.12 operating-system matrix and automated lock, formatting, lint, strict-type, and network-independent test gates; it requires a module README describing triggers, commands, platform coverage, and the prohibition on live upstream acquisition.
- **Project documentation**: Owns the project-root setup and inspection commands, provenance, third-party attribution, and data-use boundary.
- **Public command contracts**: The project-root setup command, inspection command, fixed cache location, stable success/failure signals, and non-destructive error behavior are externally observable contracts for developers and automation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On each supported verification runner, the network-independent first-acquisition test using a local bare Git remote completes in under 10 minutes, measured as wall-clock time from setup-process start through validated promotion and successful exit. Public-upstream transfer is outside this timing gate because the fixture performs no network access.
- **SC-002**: All three required operating-system matrix jobs—`ubuntu-latest`, `windows-latest`, and `macos-latest`, each using Python 3.12, Git, uv, and locked dependencies—pass the first-acquisition test without an API key or undocumented manual step.
- **SC-003**: Re-running setup against the approved checkout succeeds in 100% of tests while offline, transfers no upstream data, and produces no checkout changes.
- **SC-004**: Tests covering an incomplete checkout, wrong upstream, wrong revision, dirty checkout, and unexpected target type each produce a distinct actionable failure and leave all pre-existing target bytes unchanged.
- **SC-005**: Validation detects 100% of tested missing, empty, wrong-kind, and unreadable required-path conditions before reporting success.
- **SC-006**: Inspection reports the exact document and task file counts and complete top-level database shape for the pinned source in 100% of verification runs, while output review finds zero document bodies, synthetic record values, task contents, or expected answers.
- **SC-007**: After setup, `git ls-files -- .cache/tau3-bench/` returns zero paths and `git check-ignore -v .cache/tau3-bench/` identifies the intended project ignore rule. A recorded review of the complete Feature 001 tracked diff from an identified baseline commit to the candidate commit MUST confirm that every changed path is project-owned and within the planned file responsibilities, every non-generated addition was reviewed for upstream-derived source, data, or evaluation content, and no acquired upstream file or content was copied into a tracked location. The review record MUST include the baseline and candidate commit SHAs, all reviewed paths, reviewer, review date, and explicit pass/fail result, and MUST NOT reproduce upstream contents.
- **SC-008**: A reviewer using only the maintained documentation can correctly identify all runtime-eligible and evaluation-only τ³-Banking inputs, the five provenance fields, both developer commands, and the feature's exclusions without consulting implementation code.

## Assumptions

- The approved pin is the official stable `v1.0.1` release available when this specification was created; its tag resolves to commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`. Changing either value requires a separately reviewed dependency update.
- Developers have a supported version-control client, basic command-line access, filesystem permissions to create the repository-local cache, and internet access for the first acquisition only.
- The supported verification matrix is Python 3.12 on the GitHub-hosted runner labels `ubuntu-latest`, `windows-latest`, and `macos-latest`. All three jobs are required. Capability-aware skips are permitted only for filesystem primitives unavailable on that operating system and must not weaken shared safety assertions.
- A correct reusable checkout is a clean checkout whose configured upstream, exact revision, tag relationship, and required data paths all validate. Local modifications and untracked files make it non-reusable until the developer resolves them explicitly.
- Document count and task count mean recursive counts of readable regular files beneath the respective required directories; counting does not authorize reading or displaying task semantics.
- High-level database structure means top-level names, value kinds, and collection record counts where applicable, not schema inference from or display of individual synthetic records.
- Later features may consume only the explicit allow-list in FR-018 and must enforce the evaluation-only boundary independently. This feature documents and verifies the boundary but does not build runtime loaders or indexes.
