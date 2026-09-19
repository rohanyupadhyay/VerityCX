<!-- Defines planned wire entities, relational invariants and durable transitions for Feature 002. -->

# Data Model: Durable Knowledge Support

**Status**: Design contract; no schema has been deployed.

## Common Rules

All external/storage payloads have closed strict schemas. Wire UUIDs are lowercase canonical UUID
strings; timestamps are UTC RFC 3339 strings. Parse them deliberately into internal UUID/datetime
values after validation. Reject unknown keys, non-finite numbers, duplicate JSON keys, booleans
where integers are expected and unsupported schema versions. Positive revisions are integers.
Database UUID/timestamptz/bigint columns preserve those meanings.

Every customer/worker conversation-scoped operation first resolves the authenticated owner and checks live status
and expiry. Client input and checkpoint contents never supply trusted owner, fence or capabilities.
All parent/child mutations lock in the order conversation, job, turn, then dependent records.
Row locks and uniqueness constraints implement these invariants, not model prompts. Trusted
maintenance instead checks deletion/expiry eligibility under the same parent lock and permits only
deletion, using the separate guard in the execution contract.

## Application Entities

| Entity | Fields and constraints | Relationships / lifecycle |
| --- | --- | --- |
| DemoPrincipal | `owner_id: UUID`, `token_digest: bytes`, `enabled: bool`; digest unique; token has at least 256 bits entropy. | Provisioned in local credential configuration, separate from conversation retention. Raw token never enters DB/checkpoints/logs. |
| Conversation | `id: UUID`, `owner_id: UUID`, `schema_version=1`, `revision: int`, `corpus_version: str`, `status: active/escalation_pending/deleted`, `customer_count: 0..100`, `active_job_id: UUID?`, creation/activity/expiry/deletion timestamps. | Parent for all content; ID server-generated and never reused; expiry is last accepted activity plus 30 days. |
| Operation | `owner_id`, `request_key: UUID`, `kind: create/turn/resume/delete`, target conversation, canonical SHA-256 request digest, resource/result reference, creation time. Unique `(owner_id, request_key)`. | Authorize first; same digest returns original result/status; different kind/target/body gives conflict. Purged with conversation. |
| Turn | `id`, `conversation_id`, sequence, request key, `text: str[1..8000]`, `status: accepted/running/completed/failed`, `result_kind: answer/clarify/abstain/unavailable/escalation/error?`, response, references, failure category, timestamps. Unique conversation/sequence; one result. | Each accepted customer message increments count once, including paused messages. Resume is not a customer turn. |
| WorkJob | `id`, conversation, optional turn, `kind: turn/resume/pause_repair`, `status: accepted/running/completed/failed`, worker UUID, monotonic `fence`, lease expiry, checkpoint pointer, sanitized `failure_code: control_failed/incompatible_state?`, `recovery: retry_with_new_pause/operator_required?`, timestamps. | One nonterminal job per conversation. Lease transfer increments fence; completed turn may still have a job finalizing its checkpoint. |
| ProviderAttempt | `turn_id`, `ordinal: 1..2`, `status: reserved/succeeded/failed`, request digest, validated result or sanitized failure, usage, start/end times. Unique turn/ordinal. | First worker claim sets immutable turn processing start and deadline; all reservations share that deadline. Reservations survive crashes. |
| Escalation | `id`, conversation, triggering turn, reason, summary up to 4000 code points, source refs, `pause_id: UUID`, `status: pending/cancelled`, created/consumed times, consumed operation ID. | At most one pending escalation/conversation. Actual external delivery is always `not_connected` in 002. |
| AuditEvent | random correlation ID, conversation/turn FK, stage/outcome/route, source IDs, elapsed milliseconds, failure category, optional model and token usage. | Acceptance event is committed with turn; final outcome updated/appended atomically with result. Local associations never copied to export. |

The schema names are `support_app` and `support_checkpoints`. A versioned, checksummed migration
ledger exists outside per-conversation content. Application migrations run under a dedicated migration
role and advisory migration lock; the runtime role has no DDL permission. Checkpointer setup runs
only through the administrative migration command, not from service startup.

A separate operational WorkerHeartbeat record contains only worker UUID and last-seen UTC time;
it has no conversation content and stale records are removed after one day. Readiness uses it to
confirm a worker has reported within 15 seconds.

## Source and Provider Wire Values

- `CorpusManifest`: schema version, corpus identity (upstream pin or explicitly synthetic), parser
  version, reviewed entry list, aggregate hash. Each entry has normalized relative path, document ID,
  SHA-256 of source bytes, knowledge classification and section IDs. Duplicate IDs/paths fail.
- `KnowledgeDocument`: exactly nonempty `id`, `title`, `content` strings; no additional fields.
  File size at most 1 MiB, UTF-8, no duplicate JSON keys. Metadata is not a source of instructions.
- `EvidenceRef`: corpus version, document ID, section ID and section hash. References must belong to
  the exact selected evidence for a provider call, not merely exist somewhere in the corpus.
- `ProviderRequest`: version 1, opaque correlation ID, current question, bounded prior messages,
  bounded evidence, remaining deadline and response schema. No owner/credential/fence/banking data.
- `ProviderResult`: version 1, disposition answer/clarify/abstain, list of claim text plus evidence
  IDs, optional clarification/abstention text, model identity and optional usage. Answers require
  at least one claim; each claim requires evidence. Result total text at most 8,000 code points.

Transport values are validated before conversion into immutable internal models. Exceptions from
SDKs and drivers are normalized into fixed error enums, never stored as arbitrary Python objects.

## Graph State

Use a TypedDict with explicit wire-compatible fields: schema version, conversation UUID, current
job/turn UUID, corpus version, route, evidence references, validated provider-result reference,
optional pause ID and bounded input context. Serialize primitives plus LangGraph's built-in
interrupt value through restricted JsonPlus; application classes and pickle fallback are forbidden.

Graph state is a working projection. Application rows decide ownership, activity, attempts, result
uniqueness and current pause. On restore, validate the pointer's conversation, job origin and corpus;
then hydrate current authorized messages and pending control input. A paused checkpoint may precede
additional accepted paused messages; its old history/revision cannot overwrite those newer rows.

The application pointer identifies the approved checkpoint ID and namespace in the same transaction
as its creation. Pending writes are guarded too. No HTTP parameter exposes thread IDs, checkpoint IDs,
namespaces, fences or arbitrary graph commands. Internal thread ID is the conversation UUID.

## State Transitions

| Trigger | Preconditions | Atomic application changes |
| --- | --- | --- |
| Create | Valid principal/new operation key | New active conversation, revision 1, operation result. |
| Accept active message | Live owner, valid limits, no active job | Insert accepted turn/job/audit/key; set active job; increment count/revision and activity. |
| Worker claim/takeover | Accepted job or expired lease | Set running, new worker token, increment fence, lease +30 seconds; first customer-turn claim sets immutable processing deadline +60 seconds. |
| Reserve provider attempt | Valid fence; count below two; deadline not expired | Persist attempt before dispatch; never reset the processing deadline. |
| Commit answer/failure | Valid fence and live parent; no terminal result | Persist one result and audit; mark turn terminal. Job remains owned until graph finalization. |
| Escalate | Active authorized conversation | Persist pending escalation/pause, terminal truthful turn result and audit; graph advances to interrupt. |
| Accept paused message | Pending escalation/no active job | Insert completed context-only turn with pending acknowledgment, update summary/count/activity; no graph/model invocation. |
| Resume | Current pause, explicit true, expected current revision, no active job | Consume pause, persist resume operation/job, cancel escalation; keep customer output gated until job completes. |
| Resume finalization | Fenced control job, consumed pause reconciled | Apply only validated interrupt continuation, set active, finish job, clear active job. No provider call or fabricated customer turn. |
| Resume terminal failure | Live parent and current fenced resume job | Mark job failed, revoke lease/token and advance fence, clear active job, retain escalation_pending and advance revision; preserve consumed pause/operation. For control_failed, atomically create a new pending escalation with a fresh pause ID and preserved context. For incompatible_state, create no retry pause and block new work pending operator remediation. |
| Finish job | Fenced finalization and approved checkpoint/reconciled terminal state | Mark job terminal, clear active job, advance revision. |
| Delete | Live authorized parent | Mark deleted, revoke fence/lease, invalidate pause; block all content reads/writes immediately. |
| Expire/purge | Expiry elapsed or deletion recorded | Deny access immediately; lock parent, remove all related state and checkpoints, remove parent last. |

Reads and identical retries do not extend expiry. Accepted paused messages and successful explicit
resume are activity; malformed/rejected/conflicting operations are not. After resume consumption,
normal submissions receive a retryable busy conflict until the control job finalizes. A second resume
with another key cannot consume the same pause; an identical key returns its existing job.

Transient control interruptions leave the same job recoverable by lease takeover; they do not
consume another pause or become terminal merely because the process restarted. A terminal
`control_failed` outcome is allowed only when reconciliation validates a compatible trusted pause
and can safely reconstruct it; otherwise use `incompatible_state` with `operator_required`. A new
explicit resume after control_failed requires the fresh pause ID, current revision and a new request
key. The old key continues to report its failed job. Fencing and replacement-pause creation are
atomic so a late failed worker cannot activate the conversation. Corrupt/unsupported state stays
blocked until operator remediation restores and validates a trusted pause under the parent lock;
only then may a fresh pause be issued. No automatic clearing or retry bypass is permitted.

## Crash Reconciliation and Deletion

Terminal customer turns never invoke the provider again. If a terminal escalation lacks a durable
interrupt, recover only the pause-finalization path using the pending escalation row. If a resume
job exists but the pause checkpoint was never saved, reconstruct that trusted pause first, then apply
the persisted continuation. An unknown/corrupt checkpoint fails closed; do not silently erase it.

Guard checkpoint writes and pointer changes with the same parent lock/fence transaction used for
application mutations. A late writer cannot bypass deletion between a precheck and a saver call.
Purge removes checkpoint rows, blobs, pending writes, operations, attempts, jobs, turns, escalations
and audit records before the parent. Retained migration/corpus records contain no conversation content.
Deletion tests must attempt writes both before and after physical purge.
