<!-- Specifies transaction boundaries, checkpoint guards and recovery behavior for durable support. -->

# Execution and Persistence Contract

## Database and Startup

Use PostgreSQL 18.6 and Psycopg async connections with `autocommit=True` outside explicit
transactions and `dict_row` rows validated into closed repository models. Use separate app and
checkpoint schemas, fixed search paths and parameterized SQL. Runtime performs no DDL; the migration
command records checksums and applies application migrations and the pinned saver setup under
administrative credentials. Unsupported version/checksum drift fails readiness.

All async process/test entry points select a Windows-compatible Selector loop before creating
connections. Pools have a maximum of 20 connections per process. Ten jobs may run concurrently,
but each conversation has one active job. The worker publishes a heartbeat every five seconds.

## Claim, Budget and Result Journal

Claim work in a short transaction using row locks and skip-locked candidate selection. Recheck
parent authorization state/expiry, set the active worker UUID and increase its fence. Lease is
30 seconds, renewed every five seconds. On first claim of a customer turn, persist
`processing_started_at` using database time and `deadline_at = started_at + 60 seconds`.
Takeover never changes those values. Resume/pause repair use no model calls.

Before each provider request, lock/check the live parent and current job fence, reject elapsed
deadline or count two, then insert ordinal reservation. Disable SDK retries and graph retry policies
around the call. A reserved call counts even if the process crashes before network dispatch.
Per-call timeout is the smaller of 30 seconds and remaining budget, with an outer timeout.
One retry may follow a transient failure if budget remains; invalid-schema output may use the same
single retry without exposing raw provider text. Backoff is at most one second and inside the deadline.

Persist a validated provider result in its attempt row before graph continuation. Replay first
reuses a succeeded compatible result for the same turn/request digest. A returned but unjournaled
result may be lost; another call can occur only if the persisted budget permits it. No exact-once
provider billing guarantee is made. If the deadline is exhausted, record a terminal failure using
the valid fence; expiration limits provider processing, not the short failure-recording transaction.

## Guarded Checkpointer

Wrap the pinned `AsyncPostgresSaver`; construct each guarded writer with a specific borrowed
`AsyncConnection`, not the pool. In one outer transaction:

1. Lock the conversation row; require existence, nondeleted state and unexpired activity.
1. Validate trusted active job ID, worker token, fence and lease against application rows.
1. Apply saver checkpoint/pending-write mutation through that same connection.
1. Publish the approved checkpoint pointer with the checkpoint write; commit together.

Cover `aput`, `aput_writes` and every mutation added by a future pinned adapter upgrade. Reads
must authorize the parent and validate restored schema, conversation, originating job and corpus.
The framework envelope may contain only restricted built-in serialization types; validate
application fields separately. Use
`JsonPlusSerializer(pickle_fallback=False, allowed_json_modules=[], allowed_msgpack_modules=[])`.
Pinned package tests already round-tripped primitives and a built-in Interrupt during research;
malformed serialization and real persisted restore remain integration tests.

Source inspection confirms the supplied connection is reused and no explicit commit escapes the
saver methods. Nevertheless, rollback tests must prove that checkpoint rows, blobs, pending writes
and the application pointer roll back together with the guard transaction. Do not ship a
preflight-check-plus-pooled-write fallback if this gate fails.

## Recovery Decisions

| Durable situation | Recovery action |
| --- | --- |
| Accepted turn, no checkpoint | Claim and start from accepted input. |
| Running turn, approved checkpoint | Take over expired lease; restore exact pointer and validate; reuse journaled output when present. |
| Attempt reserved, no result | Count it as spent; another call only with remaining deadline/attempt. |
| Terminal normal turn, unfinished job | Never invoke provider; finish/reconcile graph bookkeeping and release job. |
| Terminal escalation, missing interrupt checkpoint | Run pause repair using existing pause ID and summary; do not republish answer or create another escalation. |
| Pending escalation with extra paused messages | Preserve latest application history; do not replay those messages through specialist nodes. |
| Consumed pause and accepted resume job | Restore/reconstruct trusted pending interrupt, apply persisted continuation once, then finalize active status. |
| Terminal resume failure | Fence the failed job and keep automation paused; publish sanitized failure and either a fresh retry pause or operator-required state as defined in the data model. |
| Unsupported/corrupt checkpoint | Categorized incompatible_state; preserve evidence, deny work, require operator remediation. |
| Deleted, expired or absent parent | Refuse customer/worker reads, reservations and writes; only eligible maintenance deletion is permitted; no recreation. |

Use the same internal conversation thread for interrupt resumption. HTTP resume never accepts graph
`goto`, `update`, thread, namespace or arbitrary resume payloads. The control job builds the
permitted `Command(resume=...)` from its durable operation only. Reexecuted interrupt nodes check
the application pause/consumption record and perform idempotent preparation.

After result commit a job may still own a lease to finalize a checkpoint or pause. Reject new
distinct work until that short finalization completes or recovery takes over. The graph projection
must not overwrite authoritative messages, ownership, budgets or terminal results. After worker
restart, scans reconcile these unfinished jobs even if the originating HTTP connection vanished.

## Deletion and Expiry

DELETE takes the same parent lock, marks deleted and invalidates the active fence before returning.
Expired rows fail all access/worker guards immediately. An hourly maintenance pass processes
eligible rows; startup performs catch-up before readiness. Purge uses a distinct trusted maintenance guard, not the live worker guard. In one transaction on
the same borrowed connection, lock the existing parent, require recorded deletion or elapsed expiry,
invalidate its worker token/lease and advance its fence, delete the thread through the saver, remove
attempts/jobs/turns/escalations/operations/audit and remove the parent last. Maintenance requires no
live job lease and permits deletion only; it cannot insert, restore or publish state. An absent
parent is an idempotent no-op. An ineligible live parent must not be purged. Rollback covers both
checkpoint and application deletions.
All delayed writes require a live parent, including pending checkpoint writes.

The deadline is 24 hours after logical deletion/expiry. Monitoring records overdue cleanup and
readiness fails while overdue work remains. Service downtime does not count as successful cleanup;
the operator must retain uptime for this SLO and record violations. No raw content is retained in
application backups, exported traces or tombstones in this demo.

## Mandatory Fault Evidence

Exercise the 20 SC-002 cases and additionally: rollback of each saver write kind, takeover while an
old provider call is in flight, delete between guard and saver mutation, purge followed by stale
pending-write attempt, reservation then crash, journal then crash, result commit before graph save,
resume consumption before Command and corrupt state/version. Inspect database records and request
counts; a returned HTTP message alone does not prove durability.
