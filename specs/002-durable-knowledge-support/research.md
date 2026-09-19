<!-- Records verified technology choices and application design decisions for Feature 002. -->

# Research: Durable Knowledge Support

**Date**: 2026-09-13
**Status**: Planning research complete; runtime acceptance remains implementation work.

## 1. Runtime and Dependency Baseline

**Decision**: Retain Python 3.12 and uv 0.12.5. Select the following direct pins for implementation;
the current project dependency and lock files are not changed during planning.

| Dependency | Selected version | Responsibility |
| --- | --- | --- |
| langgraph | 1.2.11 | Typed graph and interrupt lifecycle |
| langgraph-checkpoint-postgres | 3.1.2 | Durable async checkpoint adapter |
| fastapi | 0.141.1 | HTTP boundary |
| pydantic | 2.13.5 | Strict closed wire/storage models |
| psycopg[binary] | 3.3.5 | PostgreSQL driver without local compiler requirement |
| psycopg-pool | 3.3.1 | Bounded async connection pools |
| uvicorn | 0.52.4 | Local ASGI server |
| langsmith | 0.12.4 | Explicit sanitized trace export |
| openai | 3.13.0 | Selected live provider adapter |
| httpx (development) | 0.28.1 | HTTP service tests |

**Evidence**: Research agent resolved the direct pins with
`uv pip compile --python-version 3.12 --universal` in temporary scratch storage and installed/imported
the selected stack. Resolution covered 51 packages. This demonstrates resolver/import compatibility,
not end-to-end graph, database, strict-mypy or live-provider correctness. Resolved checkpoint core
was 4.2.0. Restricted serializer round trips for primitives and a built-in Interrupt passed against
the installed selected packages. Implementation must commit
the complete resulting uv lock and verify the actual boundary types without unchecked casts.

**Sources**: Maintainer package metadata:
[LangGraph](https://pypi.org/project/langgraph/1.2.11/),
[checkpoint adapter](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/),
[FastAPI](https://pypi.org/project/fastapi/0.141.1/),
[Pydantic](https://pypi.org/project/pydantic/2.13.5/),
[Psycopg](https://pypi.org/project/psycopg/3.3.5/),
[pool](https://pypi.org/project/psycopg-pool/3.3.1/),
[Uvicorn](https://pypi.org/project/uvicorn/0.52.4/),
[LangSmith](https://pypi.org/project/langsmith/0.12.4/),
[OpenAI SDK](https://pypi.org/project/openai/3.13.0/),
[HTTPX](https://pypi.org/project/httpx/0.28.1/).

**Rationale**: One async Python process model fits the existing toolchain. Binary Psycopg supports
native local installation. Its async connection rejects the Windows Proactor event loop; API,
worker, maintenance and async test entry points must select a compatible Selector loop before startup.
Use no reload or multiprocess server mode in the baseline.

**Alternatives considered**: A synchronous graph blocks concurrent calls; extra ORM, vector-database
and agent-framework layers add no required capability here. Use SQL migrations and typed Psycopg
repositories, with no SQLAlchemy or Alembic dependency.

## 2. Live Provider and Budget

**Decision**: Use the OpenAI Responses API through one adapter, with
`gpt-4.1-mini-2025-04-14` as the initial reproducible model snapshot. The official model page lists
that snapshot, Responses support and structured output support.
[Model reference](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

**Rationale**: A fixed model provides a repeatable knowledge baseline; this is not a newest-model or
quality claim. Use an explicit live mode and `OPENAI_API_KEY`; synthetic deterministic mode is the
default and makes no external request. Set `store=false`, request a closed output schema, disable SDK
automatic retries with `max_retries=0`, and enforce an outer deadline as well as the SDK timeout.
The inspected SDK defaults to two automatic retries, which would otherwise bypass the product budget.

**Decision**: The initial LangGraph router is deterministic and conservative, with no provider calls.
It recognizes explicit human requests first, unsupported operational requests second, and ambiguous
intent as clarification. Knowledge generation gets at most two persisted attempts within 60 seconds
from first processing. This preserves a retry without spending the budget on a separate classifier.
Ambiguous or mixed operation/knowledge requests never authorize tools.

**Alternatives considered**: An LLM classifier adds a paid call and another failure surface. Multiple
provider adapters are deferred until a second implementation is needed. Both selected adapters must
pass the same result contract; deterministic results cannot satisfy live grounding acceptance.

## 3. PostgreSQL, Fencing and Recovery

**Decision**: Target native PostgreSQL 18.6. The official release/version pages identify this supported
release. Native `psql` and `pg_ctl` were not found on this session's PATH; no server was installed or
modified during planning. [PostgreSQL version policy](https://www.postgresql.org/support/versioning/)

**Decision**: Application rows own identities, turn acceptance, budgets and committed results.
LangGraph checkpoints own resumable execution state. Use a guarded async saver: parent row lock,
live/expiry/fence checks, checkpoint or pending-write mutation and pointer publication all share
one database connection and short transaction. Apply guards to both `aput` and `aput_writes`.

**Rationale**: A lease preflight followed by an unguarded saver call races with takeover and deletion.
Every late writer must require an existing live parent. PostgreSQL row locks serialize conflicting
changes until transaction end.
[PostgreSQL locking](https://www.postgresql.org/docs/18/explicit-locking.html)

**Decision**: A monotonically increasing fence and random worker token protect all writes. Reserve
provider attempts before dispatch; journal validated provider results durably before graph progress.
Recovery reads the application turn and published checkpoint pointer, never an unqualified latest
checkpoint. Terminal results override checkpoint lag. A crash after reservation conservatively
consumes the attempt. A crash before result journaling may repeat a call within the remaining budget.

**Alternatives considered**: Checkpoint-only idempotency cannot enforce customer ownership or prevent
duplicate published answers. A long transaction across a model call holds locks too long. A second
queue/broker is unnecessary for 10 active conversations; PostgreSQL accepted-work polling suffices.

## 4. Interrupts and Safe Serialization

**Decision**: Persist primitive application wire values and validate them using strict Pydantic
models with extra fields forbidden. Use a restricted JsonPlus serializer with pickle fallback
disabled and explicit empty application-module allow-lists; test built-in interrupt round trips.
Never persist provider SDK objects or dynamically import application classes on restore.

**Rationale**: Strict schema validation and serializer constructor restrictions solve different
problems. JSON UUID/time strings must be parsed through intentional wire fields; do not depend on
incidental coercion differences between JSON and Python validation.
[Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)

**Decision**: Escalation commits the pending record and truthful answer before the interrupt.
Resume consumes its pause once and inserts a durable control job. Replay observes that command
record instead of creating another escalation. A crash before the interrupt checkpoint is repaired
from the pending application record. Same-thread interrupt continuation reexecutes the interrupted
node, so pre-interrupt work must be idempotent.
[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

**Sources**: Research inspected the official
[async saver source](https://raw.githubusercontent.com/langchain-ai/langgraph/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py)
and [serializer source](https://raw.githubusercontent.com/langchain-ai/langgraph/main/libs/checkpoint/langgraph/checkpoint/serde/jsonplus.py).
Moving-source findings are supported by selected-package inspection; pinned-adapter transaction and
restore tests remain mandatory implementation checks, not waived risks.

## 5. Corpus Format and Retrieval

**Decision**: Parse only closed JSON documents with string `id`, `title` and `content` fields.
Current local inspection found 698 such documents and a largest file of 8,153 bytes; only aggregate
schema metadata was emitted, not source bodies or banking records. Production source identity
remains the exact pin in Feature 001.

**Decision**: Build a reviewed source manifest and deterministic lexical section index under ignored
runtime storage. JSON content is treated as Markdown/plain text, split at headings and paragraphs,
with bounded sections and ordinal anchors. Rank by normalized token overlap with document-frequency
weighting and stable ID tie-breaks; no embeddings, web fetching or document-following tools.

**Rationale**: The observed corpus is JSON, not loose Markdown files. Parsing a closed envelope avoids
silently indexing metadata or unknown fields. A reviewed manifest labels every eligible file as a
knowledge document and records hashes. Paths alone cannot identify evaluation content copied into an
otherwise allowed directory; pinned provenance plus manifest review and deny-canary tests are needed.

**Alternatives considered**: A vector service adds infrastructure before a measured retrieval need.
Reading the banking database is unnecessary. Existing complete acquisition validation stays a
developer prerequisite; runtime document access must not invoke a reader of tasks or banking records.

## 6. Authentication, Privacy and Operations

**Decision**: Loopback service, server-provisioned random bearer tokens mapped to synthetic owners,
constant-time token digest comparison and no caller-specified ownership. Keep raw tokens in ignored
local credential material. No real banking verification, external handoff or public ingress.

**Decision**: Export only explicitly assembled metadata to LangSmith after durable local audit.
Disable ambient raw graph/SDK tracing; do not merely mask the top-level span while nested calls
capture text. Test intercepted export payloads for seeded canaries.
[LangSmith privacy controls](https://docs.langchain.com/langsmith/mask-inputs-outputs)

**Decision**: A maintenance loop scans hourly, blocks expired rows immediately and removes associated
content within 24 hours. Deletion revokes fences before purging checkpoint blobs, pending writes,
results, attempts, operation keys and audit rows. No resurrection through missing-parent upserts.
Local PostgreSQL is assumed available for scheduled cleanup; downtime is recorded as a retention
SLO violation and startup performs catch-up before readiness, never a claim of cleanup while offline.

**Alternatives considered**: Full identity-provider integration and production backup/trace retention
belong to deployment work. Standard-library JSON logs and optional explicit trace export meet this
increment without raw prompt logging.

## Resolution Summary

Provider/model, direct dependency pins, native database target, Windows event loop, source schema,
retrieval bounds, wire validation, concurrency, recovery, interrupt handling, retention and trace
privacy have selected designs. There are no unresolved product clarification markers. Remaining
implementation proofs are enumerated in the plan and quickstart; research does not satisfy them.
