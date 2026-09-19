<!-- Defines post-implementation validation commands and evidence gates without claiming they have run. -->

# Quickstart and Validation: Durable Knowledge Support

**Status**: Knowledge MVP implemented through T038; recovery/escalation and final acceptance remain
in progress. Commands for unfinished stages below are design contracts, not passing acceptance. Run all commands from the Git repository root.

## Prerequisites

- Python 3.12, uv 0.12.5, Git 2.34 or newer and the implemented/locked Feature 002 dependencies.
- Native PostgreSQL 18.6 with `psql`, `createuser` and `createdb` on PATH and server running.
  Install using the [official platform instructions](https://www.postgresql.org/download/).
  No Docker requirement. This planning session did not find those database tools on PATH.
- A database administrator for first-time database/role creation, and a separate least-privilege
  runtime role. No existing unrelated database may be reset or reused by validation.
- Live suites only: provision `OPENAI_API_KEY` through the local environment. Tracing is optional.

## Current Documentation Checks

These commands are available before Feature 002 implementation:

```powershell
uv run mdformat --check specs/002-durable-knowledge-support docs
& ./.specify/scripts/powershell/check-prerequisites.ps1 -Json
git diff --check
```

Prerequisite resolution must name this feature and its plan. It does not validate runtime behavior.

## Local Database and Environment

After PostgreSQL installation, use administrator credentials interactively:

```powershell
psql --version
createuser -U postgres --pwprompt --no-superuser --no-createdb --no-createrole veritycx_support
createdb -U postgres veritycx_support
createdb -U postgres veritycx_support_test
```

If any named role/database exists, inspect ownership and purpose before reuse; do not drop it.
Creation above is a one-time setup. Configure `VERITYCX_DATABASE_URL` for the runtime role on
`veritycx_support`, `VERITYCX_MIGRATION_DATABASE_URL` for the administrator on that same database,
and `VERITYCX_AUTH_FILE` for the generated ignored auth file. Supply passwords through your local
secret mechanism rather than committing DSNs or putting passwords in command arguments.
Migration creates schemas and grants runtime DML without schema creation privileges.

For integration validation, use a separate process environment with the equivalent URLs targeting
`veritycx_support_test`. The validation driver must require an explicit test-database identity and
own only its created fixture records; it must refuse a production/default database.

## Initialize the Implemented Demo

```powershell
uv sync --locked
uv run python scripts/manage_support.py db migrate
uv run python scripts/manage_support.py auth init-demo
uv run python scripts/manage_support.py corpus prepare --mode synthetic
```

Review the safe manifest summary and approve its printed hash:

```powershell
uv run python scripts/manage_support.py corpus approve --hash $manifestHash
```

Set `$manifestHash` to the digest printed by prepare. Approval must reject changes since prepare;
it never permits new source directories. Token setup prints ignored file paths only and refuses to
overwrite existing credentials. Raw tokens must not be copied into tracked evidence.

Start the API and worker in separate root terminals with the same configured runtime environment:

```powershell
uv run python -m veritycx.service.main
```

```powershell
uv run python -m veritycx.orchestration.worker
```

Both launchers set the Windows Selector loop when applicable. Wait for
`GET http://127.0.0.1:8000/health/ready` to report ready. The worker is required for readiness and
durable processing; process liveness alone is insufficient.

Use the [HTTP contract](contracts/http-api.md) with a generated demo client credential: create a
conversation, submit a fixture question using a fresh UUID key and poll the returned location.
Expect a fixture-supported answer with document/section citations. Repeat the same message/key;
expect the same turn/result. Request a human; expect pending escalation and an explicit statement
that nobody was notified. A second owner must receive 404 for this conversation.

## Offline Acceptance

In the dedicated test-database environment, the validator owns its API/worker subprocesses on an
available loopback port and controls their termination/restart. It must never kill unrelated
processes. No paid credentials, official checkout or trace service is required.

```powershell
uv run python scripts/manage_support.py db migrate
uv run python scripts/validate_support.py --suite offline
uv run pytest tests/support/unit tests/support/contract
uv run pytest tests/support/integration tests/support/acceptance -m "not live"
```

Register `live` and `support_db` markers; normal collection must exclude live execution unless explicit live
authorization/configuration is supplied. Missing PostgreSQL is a failure for the integration job,
not a successful skip. Ordinary three-OS fixture tests may run without it as a separately named job.
Mark all database-dependent tests `support_db`; the three-OS selection is
`-m "not support_db and not live"`, while the native database job includes `support_db`.

Required evidence:

| Gate | Expected result |
| --- | --- |
| SC-002 | All 20 specified recovery cases preserve accepted messages and unique results. |
| SC-003 | All 30 minimum adversarial cases prevent forbidden access/state effects. |
| SC-004 | All six escalation cases preserve context and truthful status. |
| SC-005 | 30 completed deterministic turns across 10 conversations, nearest-rank p95 at most five seconds; record CPU/OS/DB/versions and include queue time. |
| SC-006 | Every accepted turn has audit metadata; no seeded secrets/bodies in intercepted exporter/error payloads. |
| SC-007 | Limits, outages, version errors, budgets and retention/deletion pass, including unfinished workers. |
| Additional execution gates | Same-transaction saver rollback, stale pending writes, pause repair and resume-command recovery all pass. |

The fault harness must record hook names, attempt counts and relevant sanitized DB row counts.
Restart tests run actual subprocesses against PostgreSQL; mocks do not prove durable behavior.
Set controlled database/application test clocks for expiry without changing the host clock.
Restore real time when the isolated fixture is disposed.

## Live Grounding Acceptance

Use synthetic corpus fixtures, the configured snapshot and explicit live credentials:

```powershell
uv run python scripts/validate_support.py --suite grounding --live
```

Freeze the 40 questions, expected facts/admissible sources and prompt/schema versions before running.
Human review applies the [grounding rubric](contracts/knowledge-provider.md): at least 18/20 supported,
10/10 unsupported and 10/10 ambiguous/conflicting outcomes must pass. Mark review pending until
actually completed; successful execution alone does not satisfy SC-001. Record provider/model,
corpus/fixture digest, case outcomes, latency, usage and unknown cost values explicitly.
This suite uses synthetic documents; it does not read benchmark tasks or report an official score.

## Official-Document Demonstration

Feature 001 acceptance remains a separate prerequisite for a release claim. Its setup and check
commands are developer validation; the support runtime itself never reads banking records/tasks.

```powershell
uv run python scripts/setup_tau3_data.py --check
uv run python scripts/manage_support.py corpus prepare --mode official
uv run python scripts/manage_support.py corpus approve --hash $manifestHash
```

Use the new printed official manifest hash. Restart API and worker with the documented
`--provider openai --corpus-mode official` flags. In the dedicated demo environment run:

```powershell
uv run python scripts/validate_support.py --suite demo --live
```

The driver creates its own demo conversation, obtains a grounded answer, restarts only its owned
worker/API processes in an isolated demo run, asks a follow-up and requests escalation. It verifies
attribution and pending status, plus an explicit resume. Standalone terminals above demonstrate
manual usage; the automated driver launches its own isolated processes and port rather than
restarting those terminals. Use the same chosen corpus/provider configuration for both.

Retain sanitized evidence under ignored `.cache/support/evidence/`; tracked summaries may include
versions, hashes, case IDs and pass/fail outcomes, never upstream bodies, tokens, customer text or
evaluation content. Review response bodies through the authenticated service and keep them only in
conversation storage, under its 30-day/24-hour lifecycle. The validation driver must not leave raw
responses in separate evidence files that escape conversation deletion.

## Final Quality and Release Record

```powershell
uv lock --check
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy --strict src scripts tests
uv run mdformat --check docs specs/002-durable-knowledge-support
uv run yamlfix --check .github/workflows/quality.yml .github/workflows/support-integration.yml
uv run pytest tests
git diff --check
```

Run the full suite with the dedicated test database and live tests excluded by default. Retain the
three-OS fixture jobs and native Linux PostgreSQL integration result, each with commit, command,
environment, duration and result. Offline success does not satisfy SC-001 or the live part of SC-008.
No runtime gate is marked passed by this planning document.

## Implementation Evidence: Setup (2026-09-18)

T001-T003: locked Python 3.12 stack installed; eight responsibility packages scaffolded.
Native PostgreSQL 18.6 from the official EDB Windows binary archive is installed only under
ignored `.cache/support/postgresql/`. An isolated cluster at `.cache/support/pgdata` listens on
127.0.0.1:55432. `veritycx_support` and `veritycx_support_test` are distinct databases with distinct
non-superuser runtime roles; the separate `veritycx_admin` owns the databases. Runtime roles lack
CREATE on public and cannot connect to each other's database through PUBLIC grants.
Local JSON connection parameters are under ignored `.cache/support/local/`; do not print or commit them.
No application schemas have been migrated yet. This is setup evidence, not runtime acceptance.

To stop/start this owned cluster from the repository root:

```powershell
& .cache/support/postgresql/pgsql/bin/pg_ctl.exe -D .cache/support/pgdata -w stop
& .cache/support/postgresql/pgsql/bin/pg_ctl.exe -D .cache/support/pgdata -l .cache/support/local/postgres.log -o '-h 127.0.0.1 -p 55432' -w start
```

Test DSNs are supplied explicitly through `VERITYCX_TEST_DATABASE_URL`; tests never discover or read
local credential files automatically. The support harness rejects absent, remote, unrelated or
option-bearing DSNs, and stops only subprocess handles it created. Live pytest cases are excluded
by default. `--link-mode=copy` avoids cross-drive hardlink warnings on this Windows environment.

### Foundation Gate (2026-09-18)

T004-T019 foundation validation: the full local suite passed **193 tests**, with **3 existing
Feature 001 filesystem-link tests skipped** because Windows lacks symlink privilege. No database
case was skipped. Support coverage includes 40 passing tests for closed models, configuration,
Selector startup, authentication, root CLI, administrative migrations, runtime DDL denial,
atomic acceptance/rollback, duplicate/conflicting keys, 100th-turn limits, concurrent claims,
lease takeover and real saver checkpoint/blob/pending-write/pointer rollback.

Commands: `uv lock --check`, `uv run ruff format --check src scripts tests`,
`uv run ruff check src scripts tests`, `uv run mypy`, and `uv run pytest tests -q` with the two
explicit dedicated test DSNs. Ruff and strict mypy passed without suppressing type diagnostics.
Python 3.12, Windows, PostgreSQL 18.6 on loopback:55432; full suite elapsed 105.97 seconds.
This is foundation evidence only; no provider calls, story acceptance or hosted-CI pass is claimed.

Migration source and `uv.lock` now have explicit LF attributes. During initial unpublished setup,
the local test migration ledger was updated from its exact verified CRLF-byte hash to the LF-byte
hash of identical SQL text; no schema/data changes occurred. Future applied migrations remain
immutable. This avoids host-specific migration checksums when the repository is cloned on Linux.

### Knowledge MVP (2026-09-18)

The support suite passed **65 tests in 15.98 seconds** before additional malformed-output and actual
driver-ownership regressions were added. The real subprocess validator passed supported, unsupported
and conflicting questions using the deterministic provider. Corpus hash:
`d93ccecdefc8d84cf264619ef4ebd8ada144db9e0f975d4cc810c33aa8069460` (40 authored source documents).
The frozen inventory has 20 supported, 10 unsupported and 10 conflicting questions. All forty
finite deterministic responses passed schema/citation checks; this is not live-model grounding.

The HTTP-to-worker test verifies durable acceptance and identical retry, a cited answer through the
actual graph/saver, foreign-owner denial, duplicate/unknown JSON rejection and body-size limits.
The SDK transport test verifies no hidden retry after a rate limit, structured output, no tools,
store=false and the 2048-token cap without a network request or real API credential.
Human requests still report escalation unavailable; US3 must replace that path before final acceptance.

A failed test initially included a local test-role password in pytest's argument representation.
That credential was immediately rotated, and test DSN objects now redact their diagnostic repr.
No secret was committed. Migration/admin credentials were not exposed. No live provider calls occurred.

### Continuity and Retention (2026-09-18)

All **20 SC-002 cases** passed: after acceptance, before response commit, after commit before
client delivery, identical retry and concurrent submission, each repeated four times with owned
API/worker processes. The before-commit hook pauses the test provider after computation and before
journal/result publication; the validator kills that handle, advances only the owned lease to
simulate expiry, then starts a normal worker. Other restarts preserve one accepted row and one result.
The matrix plus four initial budget/retention cases passed in **167.53 seconds**.

Additional real-database checks passed for corrupt-pointer/operator blocking, terminal-key budget
exhaustion, DELETE authorization/retries, missing/expired parents and maintenance rollback after
actual saver deletion. Cleanup revokes fences, deletes checkpoint/application state in one transaction
and removes the parent last; live-parent purge is refused. Worker startup catches up, then scans
retention hourly; readiness rejects overdue backlog. Storage outage returns 503 without acceptance.

SC-005 local evidence: **30 turns / 10 concurrent conversations**, **p95 2.5 seconds**, zero detected
cross-owner or cross-conversation leakage, production one-second scan. Windows 11 build 26200,
Python 3.12.14, PostgreSQL 18.6, deterministic provider. Aggregate evidence only is saved under
ignored `.cache/support/evidence/load.json`. This does not establish live-provider latency.

## US3 local evidence (2026-09-19)

Native PostgreSQL 18.6, Python 3.12.14 and the deterministic provider: escalation,
resume contracts, missing-interrupt repair, fresh-pause retry/fencing, corrupt-state
operator blocking and the six-case subprocess handoff passed (13 selected tests,
23.89 seconds, including the isolated recovery regression). Ruff and strict mypy
passed for source, scripts and support tests. No model or trace service was called.

A broader intermediate run returned 104 passes and one `fault_hook_timeout` in
`before_commit-3` while an independent subprocess test was started against the same
database. The isolated regression passed. Database suites must run sequentially;
this intermediate run is not recorded as a clean full-suite result. Final full-suite
and hosted evidence remain pending.

## Final local implementation checks (2026-09-19)

The complete repository offline command returned **300 passed, 3 skipped in 328.01
seconds**. The three skips are existing Feature 001 Windows symbolic-link privilege
cases (WinError 1314); no database test was skipped. Native PostgreSQL 18.6 was used
with separate runtime/migration roles and the deterministic provider.

After that run, an additional unexpected-exception privacy test first reproduced
raw ASGI exception propagation and then passed with the new sanitized middleware.
Live-demo evidence now includes provider, model, corpus and prompt identifiers.
The final offline validator reruns all support tests after these changes. No paid
model calls, hosted workflow runs or human grounding reviews were performed.

Locked installation, Ruff format/lint, strict mypy (96 files), maintained Markdown,
workflow YAML and whitespace checks pass locally. Package README/module-docstring
inventory found no missing entries, and no ignored credential/cache artifacts are
listed by Git. PostgreSQL credentials remain in ignored local files.

The final `scripts/validate_support.py --suite offline` command completed successfully
after rerunning all support tests. Its additional HTTP scenarios reported three
knowledge cases and six handoff cases passed against the approved synthetic corpus.
This supplies the local portion of T068; T068 stays open for the three-OS and native
PostgreSQL hosted-job evidence. T069 and T070 remain open: no live credentials were
used, no paid run was made, and no human semantic review was supplied.

Implementation verification does not imply convergence: the subsequent read-only
assessment may append focused remediation tasks for gaps not exercised by the
current regression suite.
