<!-- Records Phase 0 decisions and alternatives for Feature 001. -->

# Phase 0 Research: Acquire τ³-Banking Data

## Decision 1: Minimal Python 3.12 and uv Project

**Decision**: Create a packaged `src` layout using Python 3.12, `.python-version`, `pyproject.toml`, a committed `uv.lock`, and uv 0.12.5 with the `uv_build` backend. Keep runtime dependencies empty; place pytest, Ruff, mypy, mdformat, and yamlfix in the development dependency group.

**Rationale**: A declared build system lets `uv run python scripts/...` import `veritycx` without shell-specific `PYTHONPATH` or source-path mutation. The Python pin prevents the host's default interpreter from changing behavior, while the lock makes developer environments reproducible across Windows, Linux, and macOS. See the official uv documentation for [projects](https://docs.astral.sh/uv/concepts/projects/config/), [running commands](https://docs.astral.sh/uv/concepts/projects/run/), and [locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

**Alternatives considered**:

- An unpackaged source tree with `PYTHONPATH=src`: rejected because it is shell-dependent and weakens the one-command contract.
- Hatchling or setuptools: workable, but unnecessary when uv's packaged-application backend already fits the required toolchain.
- Console entry points: deferred because the required public commands explicitly invoke repository scripts.

## Decision 2: Standard-Library Configuration and Data Parsing

**Decision**: Parse the fixed TOML pin with Python 3.12 `tomllib` and `db.json` with `json`; validate untyped input into frozen typed dataclasses. The production CLI offers no URL, tag, SHA, path, or config override.

**Rationale**: The standard library covers the complete Feature 001 format surface, so no runtime parser dependency is needed. A closed production configuration prevents unreviewed sources or destinations from bypassing provenance controls. See [Python `tomllib`](https://docs.python.org/3.12/library/tomllib.html).

**Alternatives considered**:

- Environment or CLI overrides: rejected because they undermine the reviewed source pin.
- Constants duplicated in both scripts: rejected because they can drift.
- A detailed database schema: deferred to the later synthetic-state consumer; this feature only needs a non-empty top-level object and safe collection shapes.

## Decision 3: Repository-Root Path Resolution

**Decision**: Each script derives the VerityCX root from `Path(__file__).resolve().parents[1]` and passes it explicitly to reusable functions. Configured paths must be relative, contain no parent traversal, resolve beneath the root, and maintain the expected checkout relationships.

**Rationale**: Script-location anchoring gives identical behavior regardless of current working directory and makes the library independently testable with a temporary explicit root.

**Alternatives considered**:

- `Path.cwd()`: rejected because a command launched elsewhere could read or write the wrong tree.
- Searching upward from the current directory: rejected because it is ambiguous in nested repositories.

## Decision 4: Typed, Non-Shell Git Boundary

**Decision**: Require Git 2.34 or newer and centralize Git execution behind a typed runner using `subprocess.run()` with an argument sequence, explicit `shell=False`, captured UTF-8 text, `check=False`, and `GIT_TERMINAL_PROMPT=0`. Validation uses `--no-optional-locks`/`GIT_OPTIONAL_LOCKS=0` so status checks do not refresh index metadata.

**Rationale**: Argument sequences are the portable Python subprocess form and avoid shell interpretation. Git documents that status may refresh the index unless optional locks are disabled, which matters for read-only `--check` and byte-stable idempotency. See [Python `subprocess`](https://docs.python.org/3.12/library/subprocess.html), [Git status](https://git-scm.com/docs/git-status.html), and [Git environment behavior](https://git-scm.com/docs/git).

**Alternatives considered**:

- Shell command strings or `shell=True`: rejected by the feature's security and portability contract.
- Plain `git status --porcelain`: rejected because it can make optional index writes.
- Library Git implementations: rejected because Git itself is an explicit prerequisite and provides the authoritative checkout semantics.

## Decision 5: Independent Origin, Revision, Tag, and Cleanliness Checks

**Decision**: Validate that the checkout is its own Git top level, has exactly one `origin` equal to the configured `.git` URL, has `HEAD` equal to the configured 40-character SHA, has the peeled configured tag resolve to the same SHA, and has empty `git --no-optional-locks status --porcelain=v1 --untracked-files=all` output.

**Rationale**: The SHA is the immutable content identity, while exact origin and tag binding independently prove provenance and release labeling. A stable porcelain format is intended for scripts and detects tracked and untracked changes without exposing filenames in diagnostics. See [Git clone](https://git-scm.com/docs/git-clone), [Git configuration](https://git-scm.com/docs/git-config), and [Git revision peeling](https://git-scm.com/docs/git-rev-parse).

**Alternatives considered**:

- Accepting SSH URLs, mirrors, or URL-normalized equivalents: rejected because the reviewed HTTPS URL is exact.
- Checking only `HEAD`: rejected because a wrong origin or locally retargeted tag could still pass.
- `git describe --exact-match`: rejected because a different tag at the same commit could be accepted.

## Decision 6: Owned Staging, Cooperative Locking, and Non-Replacing Promotion

**Decision**: For a missing target, atomically claim a setup lock under `.cache/`, create a unique current-run-owned staging parent with `tempfile.mkdtemp()`, clone into its nonexistent `checkout/` child, validate fully, recheck target absence, and rename within `.cache/` without replace semantics. Cleanup records exact owned paths and never globs, repairs, or removes pre-existing state.

**Rationale**: Staging keeps a failed clone distinguishable from the final dependency. Same-parent promotion avoids cross-filesystem copies, the cooperative lock serializes supported setup invocations, and exact ownership makes cleanup safe. Python 3.12 returns an absolute unique path from `mkdtemp`. Ordinary POSIX rename can replace an empty directory, so promotion uses Windows' documented no-replace `os.rename` behavior, Linux `renameat2(..., RENAME_NOREPLACE)`, or macOS `renamex_np(..., RENAME_EXCL)` and otherwise fails closed. See [Python temporary files](https://docs.python.org/3.12/library/tempfile.html), [Python rename semantics](https://docs.python.org/3.12/library/os.html#os.rename), [Linux exclusive rename](https://man7.org/linux/man-pages/man2/renameat2.2.html), and [macOS exclusive rename support](https://developer.apple.com/documentation/foundation/urlresourcekey/volumesupportsexclusiverenamingkey).

**Alternatives considered**:

- Clone directly into `.cache/tau3-bench/`: rejected because failure leaves an incomplete final target.
- Fetch/reset/repair an existing checkout: rejected as destructive and contrary to explicit error behavior.
- `os.replace()` or `Path.replace()`: rejected because replacement semantics can overwrite existing data.
- Automatic cleanup of stale staging or locks: rejected because only the current run can prove ownership.

## Decision 7: Minimal Data Validation and Safe Inspection

**Decision**: Validate document and task directories by non-following recursive enumeration, regular-file checks, non-empty counts, and minimal readability opens. Parse only the application-safe `db.json`, requiring a non-empty top-level JSON object. Inspection derives a safe summary, repeats checkout identity, cleanliness, required-path, count, and database-shape validation, and reports tag, SHA, counts, and sorted top-level collection name/kind/direct-count values only when both observations agree.

**Rationale**: The pinned Git identity authenticates evaluation tasks; decoding their contents provides no setup value and expands the leakage surface. Database parsing is required to detect malformed JSON and produce the requested high-level structure, but nested records never enter the report. Python 3.12 link and junction checks support safe traversal; see [Python `pathlib`](https://docs.python.org/3.12/library/pathlib.html).

**Alternatives considered**:

- Parsing task JSON: rejected because evaluation semantics are not needed for acquisition or counting.
- Printing filenames, samples, nested keys, or raw decode errors: rejected as avoidable source/evaluation disclosure.
- Using `os.access()` as proof of readability: rejected because opening is the authoritative operation.

## Decision 8: Stable CLI Results and Errors

**Decision**: Return `0` for success, `1` for expected operational errors, and argparse's `2` for usage errors. Success summaries go to stdout; exactly one categorized diagnostic goes to stderr with safe context and recovery guidance, without tracebacks, checkout status entries, raw JSON, arbitrary exception text, or evaluation content. A changed observation during inspection uses `checkout-changed` and emits no partial stdout.

**Rationale**: The conventional three-code model is cross-platform and easy for developers and automation to consume; stable error categories provide detail without proliferating exit codes.

**Alternatives considered**:

- A unique process exit code per failure: rejected as brittle and unnecessary.
- JSON output: deferred because the feature requests a developer inspection command, not a public machine API.
- Raw exception or subprocess dumps: rejected because they can disclose content and create platform-dependent contracts.

## Decision 9: Local-Git Test Fixtures and Canary-Based Non-Disclosure

**Decision**: Build temporary local repositories and bare remotes during pytest, inject dynamic test config and SHAs into the reusable library, and use unique canaries in document, database, prompt, expected-answer, reference-action, and grading fields. Assert canaries are absent from result fields, stdout, stderr, diagnostics, exception text, report representations, and serialized summaries. Conflict tests snapshot bytes, object/link identity, exposed permissions, Git state, and neighboring cache entries while excluding access timestamps.

**Rationale**: Local Git exercises real clone, tag, revision, origin, and cleanliness behavior without network access. Canary assertions directly prove that evaluation-only and record-level data cannot escape through success or error paths.

**Alternatives considered**:

- Cloning the official GitHub repository in tests: rejected because it is slow, network-dependent, and unsuitable for deterministic CI.
- Mocking every Git command: rejected because it would not validate real Git behavior; narrow injection remains useful for deterministic permission and failure branches.
- Committing sample upstream task content: rejected; tests generate synthetic data at runtime.
