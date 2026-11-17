<!-- Records the user-authorized automatic corpus startup implementation and checks. -->

# Automatic Knowledge Startup Implementation Plan

**Goal:** Starting the customer app acquires and initializes the pinned official knowledge
corpus when absent, and validates and reuses it on subsequent starts.

**Architecture:** Keep acquisition, resource installation, manifest preparation, and source
verification in their existing boundaries. A startup-only helper initializes the selected
corpus once. The customer launcher defaults to official knowledge for OpenAI and synthetic
knowledge for explicit deterministic mode, and passes the selection to both child processes.
The user's request authorizes initial manifest activation; changed active data still fails
validation and is never silently reapproved. Low-level API/worker entry points stay read-only.

**Tech Stack:** Existing Python 3.12, uv, Git, lexical retrieval, and manifest contracts.

## Constraints and review focus

- Keep source pins and the documents-only allow-list; do not ingest tasks or banking records.
- Reuse a valid active corpus without downloads or manifest writes.
- Preserve invalid checkouts, changed active sources, and invalid language assets.
- Fail startup on initialization errors before launching either child; never fall back to fixtures.
- Keep simultaneous initialization from racing activation; release only the current call's lock.
- Do not make paid provider calls while preparing or checking readiness.

## Tasks

- [x] Add failing lifecycle tests using temporary documents and real manifest operations:
  initial activation, repeat stability, changed-source rejection, invalid-document rejection,
  and lock ownership. Mock only acquisition/resource-install boundaries where needed.
- [x] Implement a typed startup corpus helper using the existing setup, resources, preparation,
  approval, and active-corpus verification functions.
- [x] Extend launcher contract tests for default official selection, explicit synthetic mode,
  identical child selection, initialization failure, and missing credentials.
- [x] Wire corpus initialization and selection into the launcher before child startup.
- [x] Update launcher, knowledge, and test documentation to describe initial automatic activation.
- [x] Run focused tests, the database-free suite, strict typing, formatting, and lint checks;
  exercise first initialization and repeated startup against the actual pinned corpus.

## Verification

- Final startup/launcher checks: 18 passed, including invalid existing language assets.
- Final database-free suite: 567 passed; final native PostgreSQL suite: 124 passed.
  Four live tests were excluded; both suites report the existing Starlette/AnyIO deprecation warning.
- Strict mypy, Ruff lint/format, changed Markdown formatting, environment contract, and
  whitespace checks passed. Checks used the installed locked environment with uv's
  `--frozen --no-sync` options after a transient remote metadata timeout.
- Official acquisition and initialization succeeded for the fixed release and all 698
  document files. Repeated initialization preserved every corpus file's bytes and mtime.
  The public policy endpoint reported 698 documents without database or provider calls.
- Independent read-only review found no critical or important issues. Its language-resource
  symlink finding was fixed and verified with failing-then-passing regression cases.
