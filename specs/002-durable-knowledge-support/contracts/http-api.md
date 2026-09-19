<!-- Defines the planned version-one HTTP boundary and observable failure semantics. -->

# HTTP API Contract

Local base URL: `http://127.0.0.1:8000`. JSON UTF-8, request body at most 64 KiB, no streaming.
All application endpoints require `Authorization: Bearer <token>`. Health endpoints expose no
customer/configuration data. All mutation endpoints require a canonical UUID `Idempotency-Key`.
Requests/responses use `schema_version: 1`, except empty DELETE input and health output.

Unknown keys, duplicate JSON keys, malformed UTF-8, empty/whitespace-only messages and invalid
identifier types fail before acceptance. Measure the 8,000 limit in Unicode code points; preserve
accepted message text exactly. New conversations use the configured reviewed corpus; clients cannot
select sources, models, owners or workflow states.

## Endpoints

| Method and path | Input | Success |
| --- | --- | --- |
| POST /conversations | `{"schema_version":1}` | 201, conversation ID, revision, status, expiry; repeat returns same creation result. |
| POST /conversations/{id}/turns | `{"schema_version":1,"message":"What is the policy?"}` | 202 after commit, operation key, turn ID, status, polling location. Paused messages may already be terminal but use the same 202 envelope. |
| GET /conversations/{id} | No body | 200, revision, workflow status, ordered turns with status/results, current pause metadata and expiry. |
| POST /conversations/{id}/resume | `{"schema_version":1,"pause_id":"<uuid>","expected_revision":7,"continue_automation":true}` | 202 after durable resume job; polling exposes accepted/running then completed or failed resume status. |
| DELETE /conversations/{id} | Empty body | 202 after access revocation; no content returned. Authorized identical retry returns 202 while deletion operation remains retained. |
| GET /health/live | No body | 200 `{"status":"alive"}`. |
| GET /health/ready | No body | 200 `{"status":"ready"}` or 503 `{"status":"not_ready"}`. |

The actual UUID in a request is required; the angle-bracket value above denotes its type. Ready
requires valid configuration, supported schema, reviewed corpus and reachable storage, a worker
heartbeat within 15 seconds and no overdue purge backlog. A missing optional trace exporter is not
a readiness failure. No provider network call is made for health.

## Response Values

Conversation output includes `conversation_id`, `revision`, `status`, `expires_at`,
`turns`, nullable `escalation` and nullable `latest_resume_operation`. Turn output contains `turn_id`, `sequence`,
`message`, `status` and nullable `result`. Customer results contain `kind`, `text`
and `citations`; each citation exposes corpus/document/section ID and title, not absolute paths.
Failed turns contain a sanitized category and explain that resubmitting the question with a new
request key starts a new attempt budget.

Escalation output contains `pause_id`, reason, summary, `status: pending` and
`delivery: not_connected`. Fixed acknowledgment: “Your request is saved. No human-support inbox is
connected, so nobody has been notified. You can choose to continue automated support.”
While resume is processing, conversation status remains `escalation_pending` and normal messages
receive busy conflict. The consumed escalation is not exposed as a currently usable pause.

`latest_resume_operation` contains `operation_id`, `status: accepted/running/completed/failed`
and nullable `failure`. Failure contains only `code: control_failed/incompatible_state` and
`recovery: retry_with_new_pause/operator_required`; it contains no internal exception text.
A transient interruption retains the existing recoverable job. Terminal failure leaves automation
paused. For `retry_with_new_pause`, current escalation metadata exposes a fresh pause ID; a retry
requires that ID, the current revision and a new request key. The original key stays failed. For
`operator_required`, escalation is null, no retry pause is available and new turn/resume requests
return 503 incompatible_state until operator remediation. GET and authorized deletion remain
available. Polling never implies that a human was notified.

The latest resume operation is sufficient for normal polling. An identical POST retry with an
older operation key returns that operation's current status and sanitized failure, even after a
newer resume exists. This keeps the conversation projection bounded.

Operation acceptance contains `operation_id` (the request key), `conversation_id`, nullable
`turn_id`, `status` and `poll_url`. This envelope never claims completion before durable result
commit. The GET projection bounds output through the 100-turn and per-result size limits; no raw
checkpoint, provider payload or internal diagnostic is returned.

## Idempotency and Authorization Order

1. Authenticate the bearer token; normalize/validate input before constructing a canonical digest.
1. Resolve owner access to the target; for identical delete retries allow lookup of that owner's
   retained deletion operation without revealing deleted content.
1. Lookup `(owner_id, request_key)`; same method/target/canonical payload returns the original
   operation and its current result. Different content, operation or target returns conflict.
1. For a new key, lock the live parent, check expiry, limits, revision where required and active job.
   Commit operation, accepted work and audit before replying. Creation locks its unique operation key.

Foreign and absent conversation IDs return the same 404. Never use a UUID as an authorization token.
Concurrent distinct turn/resume operations are rejected before insertion with retryable 409.
Identical retries are checked before busy/count limits so the 100th message remains retryable.
Same-key terminal failures stay terminal. After records are purged, conversation-targeting requests
return 404; a new explicit create call can create only a new server-issued conversation ID.

## Error Contract

Envelope: `{"schema_version":1,"error":{"code":"...","retryable":false,"correlation_id":"..."}}`.
Do not reflect submitted text, token values, SQL, file paths or upstream error strings.

| HTTP | Codes | Semantics |
| --- | --- | --- |
| 401 | unauthorized | Missing/invalid/disabled credential; no owner/resource details. |
| 404 | not_found | Absent, foreign, expired or deleted resource. |
| 409 | idempotency_conflict, busy, stale_resume, conversation_limit | Only busy is retryable with unchanged input. Other conflicts require corrected/new intent. |
| 413 | payload_too_large | Body exceeds 64 KiB. |
| 422 | invalid_input | Invalid schema or message length/content; no accepted turn. |
| 503 | storage_unavailable, not_ready, incompatible_state | No new acceptance; incompatible state requires operator action. |

Provider errors occur after acceptance and are exposed as terminal turn results, not retroactive HTTP
acceptance failures. Distinguish timeout, attempt_exhausted, provider_unavailable, invalid_output and
corpus_changed. No raw exception is returned. Trace export errors remain internal metadata.

## Required Contract Tests

Test every method with two distinct owners, every malformed input category, absent/foreign equality,
same-key concurrent creation/turn/resume, conflicting digest, 100th-turn retries, deletion retries,
stale pauses, busy control jobs, failed-resume polling, fresh-pause retries, operator-blocked
corrupt state and storage outage before acceptance. Test health without credentials
and verify no internal configuration is disclosed. Use real database integration for uniqueness and
commit-order guarantees; HTTP mocks alone cannot prove them.
