<!-- Defines the implementation approach, constitution gates and validation ownership for Feature 002. -->

# Implementation Plan: Durable Knowledge-Support Workflow

**Branch**: Git branch `main`; Spec Kit logical feature `002-durable-knowledge-support`.
**Date**: 2026-09-13
**Spec**: [spec.md](spec.md)
**Input**: `specs/002-durable-knowledge-support/spec.md`
**Status**: Phase 0 research and Phase 1 design complete; implementation not started.

## Summary

Deliver grounded knowledge answers, restart-safe conversations and truthful pending escalation.
Use a deterministic LangGraph intent router, one knowledge provider, strict boundary models,
FastAPI polling endpoints and PostgreSQL-backed execution. Application transactions govern
authorization, accepted turns, budgets and committed answers; guarded checkpoints preserve progress
without granting authority. The model cannot execute banking tools or change ownership.

This plan implements Feature 002 only. Chatwoot delivery, account/transaction specialists, banking
database access, embeddings, Docker, public hosting and official benchmark evaluation remain outside
scope. Feature 001 acceptance obligations are retained in the [roadmap](../../docs/platform-roadmap.md).

## Technical Context

**Language/Version**: Python 3.12; uv 0.12.5; existing strict mypy/Ruff conventions.

**Primary Dependencies**: langgraph 1.2.11, langgraph-checkpoint-postgres 3.1.2, fastapi 0.141.1,
pydantic 2.13.5, psycopg[binary] 3.3.5, psycopg-pool 3.3.1, uvicorn 0.52.4, langsmith 0.12.4,
openai 3.13.0; httpx 0.28.1 for tests and explicit metadata-only REST export. Resolved checkpoint core is 4.2.0. Exact transitive versions
will be committed through uv.lock during implementation; [research](research.md) records verification.

**Storage**: Native PostgreSQL 18.6, separate application/checkpoint schemas, ignored local corpus
manifest/index and credentials. No ORM, vector store, bank-state import or retained demo backups.

**Testing**: Existing pytest, Ruff, mypy, mdformat and yamlfix; HTTP contract tests, real PostgreSQL
fault/concurrency tests and offline synthetic provider. Separate opt-in live grounding review.

**Target Platform**: Local Windows/Linux/macOS Python entry points. Selector event loop on Windows
for all async entry points. Real database integration runs on Ubuntu CI with native PostgreSQL;
three-OS existing fixture/unit gates remain. No Docker service dependency in this feature.
Register `support_db` and `live` pytest markers. The three-OS job selects
`-m "not support_db and not live"`; the native database job runs the full offline suite with
`-m "not live"`, including the required database tests. Missing database setup fails that job.

**Project Type**: Python package plus local API, worker and developer/maintenance commands.

**Performance Goals**: SC-005: 10 simultaneous conversations, three turns each, deterministic
provider, p95 at most five seconds and zero leakage. Record environment and nearest-rank p95;
do not apply this target to live providers.

**Constraints**: 8,000 Unicode code points/message; 100 customer turns/conversation; two model
attempts/turn; persisted 60-second deadline; 30-day idle expiry and 24-hour purge deadline.
One active turn/control job per conversation; no model/credential dependence in ordinary CI.

**Scale/Scope**: One organization, synthetic users, English knowledge support; 10 worker slots,
20 connections per process maximum and a one-second work scan in both normal and acceptance runs.
Use a 30-second lease, heartbeat every five seconds and database-clock fencing. Accepted queued
work has no processing deadline until first claim; queue wait is included in latency reporting.

## Constitution Check

Pre-research review: all six principles can be met without exceptions. Post-design review:
all pass at design level with the following required implementation evidence.

| Principle | Design response | Implementation gate |
| --- | --- | --- |
| I: module READMEs | Every new responsibility package and test module receives a README. | Purpose, contracts, dependencies, configuration, root commands and failure modes reviewed. |
| II: conventional file comments | Python docstrings, SQL/YAML/TOML comments and Markdown HTML comments. JSON fixture/lock/generated artifacts use no fake comment fields. | File inventory and formatter checks. |
| III: documented interfaces | Public contracts below define inputs, failures, state and authorization; private functions also require docstrings. | Documentation review, Ruff and readable invariant comments. |
| IV: strict typing | Closed Pydantic wire models, explicit protocols, typed graph state and validated DB rows. Restricted serialization; no unchecked casts, Any leakage or blanket ignores. | Strict mypy across source/scripts/tests and malicious-payload tests. |
| V: automated quality | Existing quality matrix retained; new docs already recursively covered; add database integration and test-mode guards. | Locked install, format/lint/type/unit and database jobs; no skip-as-pass release evidence. |
| VI: one repository root | All package/config/test/spec files and commands stay at Git top level. | Existing repository-layout tests and entry-point smoke checks. |

No constitution amendment or exception is required. Selected package imports and serializer checks
are research evidence; actual application strict typing and PostgreSQL atomicity remain required
implementation gates.

## Project Structure

### Documentation (this feature)

```text
specs/002-durable-knowledge-support/
  README.md
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  checklists/requirements.md
  contracts/
    README.md
    http-api.md
    execution.md
    knowledge-provider.md
    configuration.md
```

`tasks.md` is the subsequent `speckit-tasks` output and is not generated by this command.

### Source Code (repository root; planned)

```text
src/veritycx/
  data_sources/                  # Existing acquisition boundary retained
  conversations/                 # models.py, commands.py, lifecycle.py
  service/                       # app.py, auth.py, routes.py, main.py
  orchestration/                 # state.py, graph.py, router.py, worker.py
  knowledge/                     # models.py, manifest.py, index.py, retrieval.py
  policy/                        # authorization.py, sources.py, outputs.py
  providers/                     # protocol.py, deterministic.py, openai.py
  persistence/                   # models.py, repository.py, checkpoints.py, maintenance.py
    migrations/                  # Versioned commented SQL and README
  observability/                 # audit.py, export.py
scripts/
  manage_support.py              # db/auth/corpus administration
  validate_support.py            # End-to-end offline/live validation driver
config/
  support.toml                   # Nonsecret defaults, fixed corpus configuration
tests/
  support/
    unit/
    contract/
    integration/
    acceptance/
    fixtures/                    # Authored synthetic documents/cases only
.github/workflows/
  quality.yml                    # Existing matrix retained
  support-integration.yml        # Native Linux PostgreSQL, no paid/network model calls
```

Each new Python package contains `__init__.py` and a responsibility README. Test/support subdirectories,
the migration directory, scripts/config and existing root READMEs document their owned additions.
The listed Python filenames partition responsibilities; task generation may split large files
without changing public contracts. No additional project root or forwarding wrappers are introduced.

## Implementation Sequence

1. Establish direct dependency pins and locked resolution, typed contracts, configuration and
   synthetic test fixtures. Validate Windows event-loop startup and restricted serializer round trips.
1. Add versioned SQL migrations, application repositories and guarded checkpoint adapter. Prove
   rollback atomicity for guard plus saver writes on one connection before graph integration.
1. Build closed JSON corpus parsing, reviewed manifest/index, lexical retrieval and source guards.
   No runtime reader reaches banking database or evaluation artifacts.
1. Implement deterministic router, policy gates and both provider adapters. Persist attempt
   reservations and reusable validated results. Implement graph recovery using published pointers.
1. Expose authenticated API and worker; acceptance acknowledgments follow transaction commit.
   Add bounded errors, health, concurrency rejection, deletion and maintenance.
1. Add idempotent pending escalation and durable resume control jobs, with interrupt crash repair.
   Subsequent paused messages are stored and acknowledged without specialist execution.
1. Complete metadata-only audit/export, test all fault windows and security categories, then run
   separate live grounding and the official-document demonstration. Record evidence, never inferred
   benchmark scores or delivery to a human.

These are design milestones, not executable task IDs. Regression tests for each state/invariant
precede its implementation in the later task list.

## Requirements and Evidence Ownership

| Requirements | Owner / contract | Evidence |
| --- | --- | --- |
| FR-001, FR-008, FR-011, FR-015, FR-017 | Service/conversations; [HTTP](contracts/http-api.md) | Cross-owner operations, duplicate/conflicting keys, limits, health and stale resume. |
| FR-002–FR-006 | Router/knowledge/policy; [knowledge/provider](contracts/knowledge-provider.md) | Frozen grounding set, routing cases, denied source/tool access, citation validation. |
| FR-007–FR-009, FR-013 | Persistence/worker; [execution](contracts/execution.md) | 20 specified recovery cases plus stale checkpoint writer and attempt-reservation faults. |
| FR-010–FR-012 | Conversations/graph/persistence | Six escalation cases, resume crash repair, schema/serializer negative cases. |
| FR-014, FR-016 | Audit/maintenance; [configuration](contracts/configuration.md) | Export canaries, audit completeness, deletion/expiry and late-worker tests. |
| FR-018; SC-001–SC-008 | Validation harness; [quickstart](quickstart.md) | Separate offline, live grounding and live demonstration records. |

Thirty adversarial minimum cases cover the six specified categories; additional tests cover
TM-01–TM-13 in the [threat model](../../docs/threat-model.md), especially transaction-level checkpoint
fencing and no-resurrection. TM-14–TM-18 remain future obligations.

## Phase Outputs and Verification

Phase 0 resolved technology, model, corpus and reliability decisions in [research.md](research.md).
Phase 1 defines [entities](data-model.md), [contracts](contracts/README.md) and the
[validation guide](quickstart.md). The implementation plan is authoritative for Feature 002
technical details; the broader platform design remains architectural context and the spec governs
product scope.

Design checks: no unresolved template placeholders, contiguous requirement references, valid local
links, conventional documentation headers, mdformat and root Spec Kit resolution. This command
does not provision PostgreSQL, install project runtime dependencies, execute paid model calls,
generate tasks or claim runtime acceptance.

## Complexity Tracking

No constitution violations. The guarded saver and turn journal are necessary to enforce deletion,
ownership and retry guarantees across separate checkpoint/application commits. A plain saver and
in-memory request cache cannot provide these guarantees; real PostgreSQL fault tests are mandatory.
