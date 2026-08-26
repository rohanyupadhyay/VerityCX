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

## Contract Authority and Precedence

- This specification is authoritative for Feature 001 scope, user-visible behavior,
  safety properties, and acceptance outcomes.
- `config/tau3-bench.toml` is the only production-readable source for the exact pin
  and path values. Code MUST NOT obtain those values from this specification,
  contracts, README files, environment variables, or command-line overrides.
- Files under `contracts/` are the normative detailed interfaces that refine this
  specification without changing it. `plan.md` defines the implementation design;
  README files and third-party notices explain the approved behavior to developers.
- Any conflict is a release-blocking defect: this specification governs intent, the
  TOML file governs production values, and all contracts, plan text, tests, and
  maintained documentation MUST be corrected in the same change. A pin, path,
  command, or policy change starts with an approved specification change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Acquire a Verified Dataset (Priority: P1)

As a VerityCX developer, I want one documented command that I can run from the project root so that I obtain the approved τ³-Banking data at the expected local cache path and know that it is the exact version the project supports.

**Why this priority**: Every later feature that uses τ³-Banking depends on developers starting from the same authentic and complete upstream data.

**Automated Independent Test**: On each supported operating system, exercise the setup workflow against a temporary local bare Git remote containing synthetic banking fixtures and verify validated promotion, required paths, stable command behavior, and absence of credential prompts.

**Manual Live Smoke Test**: Before release, run the documented setup command from one clean developer clone against the fixed official upstream pin and verify the installed origin, tag, commit SHA, and required banking paths.

**Acceptance Scenarios**:

1. **Given** a clean clone and network access, **When** a developer runs the documented setup command from the project root, **Then** the official τ³ repository is acquired at `.cache/tau3-bench/` at tag `v1.0.1` and commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`.
1. **Given** the approved checkout is present, **When** setup validates it, **Then** the documents directory, synthetic database file, and tasks directory are all confirmed present, non-empty where applicable, and readable.
1. **Given** setup has completed, **When** repository tracking is inspected, **Then** `.cache/tau3-bench/` and all content below it are excluded from version control and no upstream source or data has been copied into a tracked VerityCX location.
1. **Given** a required Windows, Linux, or macOS verification runner and a synthetic local-Git fixture, **When** the same setup workflow and command contract are exercised, **Then** they complete without operating-system-specific manual data handling.

______________________________________________________________________

### User Story 2 - Re-run Setup Safely (Priority: P2)

As a developer with an existing cache, I want setup to distinguish a valid cache from an unsafe or incorrect one so that routine re-runs are fast and my local files are never silently replaced.

**Why this priority**: Reproducibility requires both idempotent success for the correct revision and non-destructive failure for every conflicting state.

**Independent Test**: Re-run setup against a correct checkout while offline, then test separate caches containing an incomplete checkout, a different remote, a different revision, and local changes; confirm only the correct checkout succeeds and every conflicting cache remains byte-for-byte unchanged.

**Acceptance Scenarios**:

1. **Given** a complete, clean checkout with the approved upstream and revision, **When** setup is run again, **Then** it succeeds without downloading the repository again or changing the checkout.
1. **Given** `.cache/tau3-bench/` exists but is incomplete, **When** setup is run, **Then** it fails with a message that identifies the missing or unreadable requirement and leaves the existing directory unchanged.
1. **Given** the cache points to a repository other than `https://github.com/sierra-research/tau2-bench.git`, **When** setup is run, **Then** it fails with a message that reports the expected and detected upstream and leaves the existing directory unchanged.
1. **Given** the cache is at any revision other than the approved commit, **When** setup is run, **Then** it fails with a message that reports the expected and detected revisions and leaves the existing directory unchanged.
1. **Given** the cache contains local modifications or untracked content, **When** setup is run, **Then** it reports that the checkout is not clean and does not delete, reset, overwrite, or otherwise alter that content.
1. **Given** any valid or invalid existing checkout and no network access, **When** default setup or `--check` validates it, **Then** the result depends only on local state and no remote contact, lock, staging directory, or cache repair is attempted.
1. **Given** two supported setup processes start with a missing target, **When** they contend for setup ownership, **Then** exactly one may acquire the cooperative lock and the other fails without modifying the owner's state.
1. **Given** another actor creates the destination before promotion, **When** setup performs its required destination recheck, **Then** setup preserves the destination, removes only its own staging and lock state, and reports a destination conflict.

______________________________________________________________________

### User Story 3 - Inspect and Use Data Responsibly (Priority: P3)

As a developer, I want a safe inspection command and clear third-party documentation so that I can confirm what was acquired and understand which portions may be consumed by VerityCX without exposing evaluation answers to the runtime agent.

**Why this priority**: Developers need a useful verification summary, while strict separation of application data from evaluation-only material protects benchmark validity.

**Independent Test**: Run the documented inspection command against the approved checkout and review the attribution and data-use documentation; verify that the summary contains counts and database shape only, and that the documented allow-list and deny-list are unambiguous.

**Acceptance Scenarios**:

1. **Given** a valid checkout, **When** a developer runs the inspection command from the project root, **Then** it reports the document count, task count, and high-level synthetic database structure without displaying document bodies, customer record values, task contents, evaluation criteria, expected answers, or golden actions.
1. **Given** a later application feature needs τ³-Banking data, **When** its permitted inputs are reviewed, **Then** only `documents/` may be used for knowledge retrieval or prompts and `db.json` may be used as synthetic banking state.
1. **Given** any runtime-agent or indexing boundary, **When** τ³ content is selected, **Then** `tasks/`, `tasks.json`, `tasks_voice.json`, evaluation prompts, evaluation criteria, expected answers, golden actions, and other evaluation artifacts are excluded.
1. **Given** a developer reviews third-party attribution, **When** they look for dependency provenance, **Then** they can find the upstream owner and URL, MIT licence, release tag, exact commit SHA, local cache location, and data-use restrictions in one maintained location.
1. **Given** inspection encounters a missing, invalid, dirty, unreadable, or detectably changing checkout, **When** validation or final consistency checking fails, **Then** inspection exits unsuccessfully without a partial summary, network access, or filesystem mutation.

### Edge Cases

- A handled first-acquisition failure before promotion removes only the staging parent and setup lock created by that invocation and leaves the final target absent. If abrupt termination or cleanup failure leaves staging or lock state behind, later runs preserve it. A surviving lock blocks setup with its exact location and manual recovery guidance; unrelated stale staging directories are never removed automatically. A partial checkout is never written to or promoted as `.cache/tau3-bench/`.
- The cache path exists as an empty directory, regular file, symbolic link, junction, non-repository directory, or unreadable directory. Setup fails safely without following, replacing, or deleting unexpected content.
- The expected tag resolves to a commit other than the recorded SHA. Setup treats the immutable commit SHA as authoritative, reports the tag mismatch, and does not accept or overwrite the checkout.
- The checkout has the correct revision but a required path is missing, empty, the wrong kind, or unreadable. Setup reports the affected path and fails validation.
- The synthetic database is readable as a file but cannot be structurally inspected. Inspection fails clearly without dumping its contents.
- Task filenames or counts change because a user modified the cache. The dirty-checkout validation prevents the modified cache from being reported as the reproducible source.
- Setup or inspection is run from outside the project root. The command either locates the VerityCX project root safely or reports the required working location without writing to an unintended path.
- The `.cache/` parent exists as a file, link, junction, special object, unreadable directory, or resolved path outside the project root. Setup and inspection reject it without following, replacing, or deleting it.
- Git or uv is missing or unsupported, configuration is missing or malformed, the upstream service is unavailable, or Git would request credentials. The command fails in its assigned diagnostic category without prompting, retrying through another source, or creating a final target.
- Two supported setup processes start concurrently, a lock already exists, or the destination appears after lock acquisition. Cooperative-lock ownership and the final destination recheck determine the result; no invocation removes another invocation's state.
- A handled failure before promotion removes only current-run-owned staging and lock state. A failure during a non-replacing promotion reports a destination conflict or operational failure and preserves the destination. A failure detected after promotion preserves the promoted checkout for manual review and never attempts rollback, replacement, or destructive repair.
- A platform exposes links, Windows junctions or reparse points, special files, case differences, permission failures, or path-length limits. The commands use filesystem-object and containment checks rather than case-folded string trust, reject unsafe objects, and fail safely when the host cannot represent or access the path.
- `db.json` is empty, malformed UTF-8 or JSON, a scalar or array at the root, an empty object, or contains scalar, empty, or null top-level values. Validation rejects every root except a non-empty object; inspection reports only the defined kind and direct count for each permitted top-level entry.
- Checkout identity, required files, permissions, or cleanliness changes while inspection validates or counts. A detected change causes the `checkout-changed` failure before any summary is printed; final validation does not claim protection against an undetectable actor that changes state and restores the identical validated state between observations.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide exactly one setup command entry point, `uv run python scripts/setup_tau3_data.py`, runnable from any current working directory. Its default mode acquires or validates the approved dependency; its sole operational flag, `--check`, selects read-only validation of the same command rather than defining a second setup command.
- **FR-002**: Setup MUST use the official upstream repository `https://github.com/sierra-research/tau2-bench.git` and store its checkout only at `.cache/tau3-bench/` relative to the project root.
- **FR-003**: The approved source pin MUST be recorded as MIT-licensed release tag `v1.0.1` at exact commit SHA `fc0055dc4e0a316c3f83133267fbd6faaa770992`; both tag and SHA MUST be verified for an acquired checkout.
- **FR-004**: `.cache/tau3-bench/` and all of its descendants MUST be excluded from version control.
- **FR-005**: No τ³ source code, banking documents, synthetic banking data, evaluation tasks, or other acquired upstream content MAY be manually copied into or committed to a tracked VerityCX location.
- **FR-006**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/` exists as a readable, non-empty directory containing readable regular files according to the objective readability rules below.
- **FR-007**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json` exists as a readable regular UTF-8 file and parses as a non-empty top-level JSON object.
- **FR-008**: Setup MUST validate that `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/` exists as a readable, non-empty directory containing readable regular files, without decoding, displaying, logging, returning, or forwarding task contents or filenames.
- **FR-009**: Re-running setup with a complete, clean checkout at the approved upstream and revision MUST succeed without contacting or downloading from the remote and without modifying the checkout. Validation of any existing invalid checkout MUST also be offline and non-mutating.
- **FR-010**: If the target or cache path contains an incomplete checkout, unexpected content, an incorrect upstream, an incorrect revision, local changes, a link or junction, an unsupported object, an ownership conflict, or a concurrently appearing destination, setup MUST fail with a categorized diagnostic and MUST NOT delete, reset, overwrite, move, repair, or intentionally modify pre-existing or unowned state. Preservation includes file bytes, link identity, permissions, Git administrative state, and neighboring cache entries; unavoidable access-time effects of read operations are excluded.
- **FR-011**: Setup MUST use exit code `0` for success, `1` for an expected operational failure, and argparse exit code `2` for invalid usage. Success fields go only to stdout; one stable diagnostic category plus the required safe context and recovery action go only to stderr; expected failures emit no traceback or partial success summary.
- **FR-012**: The project MUST provide one documented inspection command, `uv run python scripts/inspect_tau3_banking_data.py`, runnable from any current working directory. It MUST apply the same non-mutating checkout and banking validation to an already acquired checkout and MUST NOT clone, fetch, repair, lock, stage, create the cache, or emit a partial summary on failure.
- **FR-013**: Inspection MUST report the recursive readable-regular-file count under `documents/`, the recursive readable-regular-file count under `tasks/`, and sorted top-level database entries. Each database entry reports one kind from `object`, `array`, `string`, `number`, `boolean`, or `null`; only objects and arrays report a direct, non-recursive entry or item count, including zero.
- **FR-014**: Inspection results and every success or expected-error channel—including stdout, stderr, diagnostics, logs, exception text, `repr`, and supported serialization—MUST NOT reveal document or task filenames or bodies, nested database keys, record identifiers or values, task instructions, prompts, evaluation criteria, expected answers, reference or golden actions, grading or reward data, raw Git status, raw commands, or source-derived snippets.
- **FR-015**: Setup and inspection MUST use the same `uv run python <script>` syntax and stable project-owned fields, modes, diagnostic categories, and exit codes on supported Windows, Linux, and macOS environments. Paths resolve from each script rather than the current directory; platform-native path separators or operating-system text may appear only in sanitized path and cause fields explicitly allowed by the command contracts.
- **FR-016**: Setup and inspection MUST require no API keys, credentials, or paid services. Every Git process MUST use argument sequences with `shell=False`, disable terminal prompting, reject credential-bearing or rewritten detected origins, and sanitize subprocess failures. A missing or unsupported Git/uv prerequisite and an unavailable upstream MUST fail without fallback credentials, an alternate source, or an interactive prompt.
- **FR-017**: Maintained third-party attribution MUST identify Sierra Research, the official upstream URL, the MIT licence, release tag `v1.0.1`, exact commit SHA `fc0055dc4e0a316c3f83133267fbd6faaa770992`, and the fact that acquired files remain external and untracked.
- **FR-018**: Maintained data-use documentation MUST define an allow-list: only banking knowledge files under `documents/` may be indexed, retrieved, or added to runtime prompts by later features, and only `db.json` may be used as later synthetic banking state.
- **FR-019**: Maintained data-use documentation MUST classify `tasks/`, `tasks.json`, `tasks_voice.json`, task instructions, evaluation criteria, expected answers, golden actions, evaluation prompts, grading or reward data, reference actions, and semantically equivalent artifacts regardless of filename or location as evaluation-only.
- **FR-020**: Inspection output MUST exclude all evaluation-only material. Maintained data-use documentation MUST define runtime agents, prompt builders, knowledge indexes, and application-facing data loaders as default-deny consumers. Every later consuming feature MUST trace each input to the FR-018 allow-list and include an acceptance gate proving that unclassified and evaluation-only inputs are rejected before any indexing, prompting, loading, API exposure, or agent use.
- **FR-021**: Every new, renamed, moved, or otherwise unclassified upstream path—including source code, prompts, examples, simulations, and files not expressly allow-listed by FR-018—MUST remain default-denied external acquisition content and MUST NOT be treated as VerityCX application data.
- **FR-022**: This feature MUST stop at acquisition, pinning, validation, inspection, and documentation; it MUST NOT add document chunking, embeddings, database import, agent workflows, web endpoints, container infrastructure, or benchmark evaluation.

### Normative Operational Definitions

- **Readable directory**: The path is a real directory, not a symbolic link,
  junction/reparse point, or special object; it can be enumerated recursively without
  following links; every encountered descendant remains contained beneath the
  configured root; and every counted regular file can be opened for a minimal binary
  read. A permission or enumeration failure is unreadable.
- **Readable regular file**: The path is a contained, non-link regular file that can be
  opened for a minimal binary read. `db.json` additionally must decode as UTF-8 and
  satisfy FR-007. `os.access()` alone is not proof of readability.
- **Setup diagnostic contract**: The stable categories are `configuration-invalid`,
  `git-unavailable`, `checkout-missing`, `unexpected-target`,
  `not-standalone-repository`, `origin-mismatch`, `revision-mismatch`,
  `tag-mismatch`, `dirty-checkout`, `banking-data-invalid`,
  `malformed-database`, `setup-locked`, `clone-failed`,
  `destination-conflict`, `checkout-changed`, and `staging-cleanup-failed`.
  Each diagnostic identifies the category, the applicable configured or owned path,
  safe expected/detected metadata where relevant, and a non-destructive recovery
  action. It never includes recursive filenames, credentials, raw source, or raw
  subprocess output.
- **Read-only `--check` contract**: `--check` permits configuration reads, filesystem
  metadata inspection, minimal required-file opens, JSON parsing, and Git commands
  with optional locks disabled. It creates no cache, lock, staging state, checkout,
  log, or report file; contacts no remote; returns the same `check` success fields as
  the setup contract; and returns `checkout-missing` when the target is absent.
- **Inspection consistency contract**: Inspection buffers its approved summary,
  repeats checkout identity, cleanliness, required-path, count, and database-shape
  validation immediately before output, and emits nothing to stdout unless both
  observations agree. A detected difference returns `checkout-changed` on stderr.
- **Preservation evidence**: Automated tests compare pre/post file bytes, link/object
  identity, permission bits where the platform exposes them, Git references/index and
  worktree status, and sibling cache entries. Tests exclude access timestamps and use
  injected permission operations where host privileges would make a native result
  nondeterministic.
- **Supported tool and filesystem baseline**: Python is exactly 3.12; Git is 2.34 or
  newer; uv is exactly 0.12.5 for the required verification workflow. The project
  path must be representable and accessible to Python and Git on the host. JSON and
  maintained configuration are UTF-8, stable CLI field names and categories are
  locale-independent, and upstream filenames are treated as opaque and never emitted.

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

The required maintained artifacts and requirement owners are:

| Requirement owner | Maintained artifacts |
|---|---|
| Pin, configuration, and containment (FR-002–FR-003) | `config/tau3-bench.toml`, `config/README.md`, `contracts/configuration.md` |
| Setup, validation, diagnostics, and recovery (FR-001, FR-004–FR-011, FR-015–FR-016) | `README.md`, `scripts/README.md`, `contracts/setup-cli.md` |
| Inspection and non-disclosure (FR-012–FR-016, FR-020) | `README.md`, `scripts/README.md`, `contracts/inspection-cli.md` |
| Provenance and external-content boundary (FR-005, FR-017, FR-021) | `THIRD_PARTY_NOTICES.md`, `docs/data/tau3-banking.md` |
| Allow-list, evaluation deny-list, and future enforcement (FR-018–FR-022) | `docs/data/tau3-banking.md`, `contracts/data-use-policy.md` |
| Constitution-required module ownership | `README.md`, `.github/workflows/README.md`, and focused READMEs under `config/`, `scripts/`, `src/veritycx/`, `src/veritycx/data_sources/`, and `tests/data_sources/` |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On each supported verification runner, one required clean-job attempt of the network-independent first-acquisition test using a local bare Git remote completes in under 10 minutes, measured with a monotonic wall clock from setup-process start through validated promotion and successful exit. The runner label and its standard hosted hardware image form the environment baseline. Infrastructure retries are recorded as separate attempts and do not replace a failed product result. Public-upstream transfer is outside this timing gate because the fixture performs no network access.
- **SC-002**: All three required operating-system matrix jobs—`ubuntu-latest`, `windows-latest`, and `macos-latest`—use Python 3.12, Git 2.34 or newer, uv 0.12.5, and locked dependencies, and pass the first-acquisition test without an API key or undocumented manual step. Retained job logs record the runner image, `python --version`, `git --version`, `uv --version`, command, result, and SC-001 duration as acceptance evidence.
- **SC-003**: Re-running default setup and `--check` against the approved checkout succeeds in 100% of tests while offline, transfers no upstream data, and produces no checkout changes. Invalid existing-checkout cases also complete without remote contact or mutation.
- **SC-004**: Tests covering an incomplete checkout, wrong upstream, wrong revision, dirty checkout, unexpected target/cache types, lock ownership, and destination races each produce a distinct actionable failure. The preservation snapshot defined above shows no change to pre-existing bytes, link/object identity, exposed permissions, Git administrative/worktree state, or neighboring cache entries.
- **SC-005**: Validation detects 100% of tested missing, empty, wrong-kind, and unreadable required-path conditions before reporting success.
- **SC-006**: Inspection reports the exact document and task file counts and complete top-level database shape in 100% of verification runs. Tests derive the expected counts and kinds independently from the synthetic fixture, include empty collections and every JSON scalar kind, and repeat validation before output. Unique canaries covering every FR-014 disclosure class occur zero times across result fields, stdout, stderr, diagnostics, exception text, `repr`, and supported serialization. The official smoke check independently enumerates counts and top-level shape from the exact pinned checkout without recording bodies, nested keys, record values, task semantics, or filenames.
- **SC-007**: After setup, `git ls-files -- .cache/tau3-bench/` returns zero paths and `git check-ignore -v .cache/tau3-bench/` identifies the intended project ignore rule. A recorded review of the complete Feature 001 tracked diff from an identified baseline commit to the candidate commit MUST confirm that every changed path is project-owned and within the planned file responsibilities, every non-generated addition was reviewed for upstream-derived source, data, or evaluation content, and no acquired upstream file or content was copied into a tracked location. The review record MUST include the baseline and candidate commit SHAs, all reviewed paths, reviewer, review date, and explicit pass/fail result, and MUST NOT reproduce upstream contents.
- **SC-008**: A reviewer using only the maintained documentation can correctly identify all runtime-eligible and evaluation-only τ³-Banking inputs, the five provenance fields, both developer commands, and the feature's exclusions without consulting implementation code.

## Assumptions

- The approved pin is the official stable `v1.0.1` release available when this specification was created; its tag resolves to commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`. Changing either value requires a separately reviewed dependency update.
- Developers have a supported version-control client, basic command-line access, filesystem permissions to create the repository-local cache, and internet access for the first acquisition only.
- The supported verification matrix is Python 3.12 on the GitHub-hosted runner labels `ubuntu-latest`, `windows-latest`, and `macos-latest`. All three jobs are required. Capability-aware skips are permitted only for filesystem primitives unavailable on that operating system and must not weaken shared safety assertions.
- Required verification uses Git 2.34 or newer and uv 0.12.5. The CI workflow pins uv, records both tool versions, and fails before tests when a prerequisite is absent or outside the supported range.
- Atomic directory creation is the cooperative setup-lock primitive. Staging and the final target share the `.cache/` parent and therefore a filesystem. Supported setup processes honor the lock; unrelated actors do not gain cleanup ownership. The destination absence recheck and non-replacing promotion are the acceptance boundary for a destination race.
- Filesystem preservation snapshots are observations, not backups. They cover the states listed in the normative preservation definition, while access timestamps and platform-inaccessible metadata are excluded and permission failures are tested through deterministic injection.
- Host path-length, access-control, and filesystem-name rules remain prerequisites: the repository root must be representable and usable by Python 3.12 and Git. Containment uses filesystem-aware resolution and object checks; it does not infer safety from case normalization or string prefixes.
- GitHub availability and unauthenticated access are needed only for the manual first-acquisition smoke check. Automated acceptance uses local bare remotes. The full SHA is authoritative if a tag is moved, exact origin text includes `.git`, URL rewrites and credential-bearing variants are rejected, and any upstream/authentication failure leaves the final target absent.
- A correct reusable checkout is a clean checkout whose configured upstream, exact revision, tag relationship, and required data paths all validate. Local modifications and untracked files make it non-reusable until the developer resolves them explicitly.
- Document count and task count mean recursive counts of readable regular files beneath the respective required directories; counting does not authorize reading or displaying task semantics.
- High-level database structure means top-level names, value kinds, and collection record counts where applicable, not schema inference from or display of individual synthetic records.
- Later features may consume only the explicit allow-list in FR-018 and must enforce the evaluation-only boundary independently. This feature documents and verifies the boundary but does not build runtime loaders or indexes.
