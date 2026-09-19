<!-- Records proposed trust boundaries, security controls and residual platform risks. -->

# VerityCX Threat Model

**Date**: 2026-09-12
**Status**: Initial design review; controls are requirements, not verified defenses.
**Scope**: Feature 002 local synthetic knowledge workflow, with future obligations marked below.
**Related**: [Specification](../specs/002-durable-knowledge-support/spec.md), [design](platform-design.md)

## Assets and Trust Boundaries

Protect conversation ownership and content, credentials, policy decisions, approved source
provenance, checkpoint integrity, request identity and audit evidence. Future assets include
synthetic account mutations, human ownership and support-platform tokens.

Boundaries are customer-to-service, service-to-conversation storage, runtime-to-approved corpus,
runtime-to-provider, runtime-to-trace exporter and, later, runtime-to-Chatwoot/tool services.
Customer text, document bodies, model output and external events are untrusted. A trusted upstream
origin does not turn its document prose into executable policy. Possessing a conversation ID, a
source citation or a model-produced claim of verification conveys no authority.

Assume attackers can craft requests, repeat or reorder operations, guess identifiers and place
hostile instructions in test documents or model output. Database administrators and a compromised
host are outside the initial application's protection boundary; host compromise defeats demo
secrets. This scope does not justify public exposure or use of real customer records.

## Threat and Control Register

| ID | Threat / concrete failure | Required control and owner | Verification / requirement |
| --- | --- | --- | --- |
| TM-01 | Customer claims to be another owner or requests a foreign checkpoint. | Service derives owner from credentials; storage checks owner on every operation; foreign/absent resources share an error. | Two-owner read/write/resume/delete tests; FR-001, SC-003. |
| TM-02 | Customer text instructs router to bypass policy or execute banking operations. | Orchestrator restricts routes; policy/tool boundaries enforce capabilities; no banking tools in 002. | Five customer-injection cases inspect effects; FR-005/006, SC-003. |
| TM-03 | Retrieved prose instructs the provider to leak secrets, alter identity or fetch hostile URLs. | Knowledge treats prose as evidence only; no URL-following or provider filesystem/network tools; closed result schema. | Five document-injection cases and outbound-capability checks; FR-003/005, SC-003. |
| TM-04 | Evaluation tasks or reference answers contaminate retrieval or prompts. | Knowledge loads only validated document allow-list, rejects evaluation semantics and unclassified paths; evaluation runner remains separate. | Forbidden-source canaries at loading, indexing and prompt boundaries; FR-003, SC-003. |
| TM-05 | Model invents citations or policy claims. | Knowledge validates source membership; provider abstains on inadequate evidence; human grounding review measures semantic support. | Supported/unsupported/conflicting question set; FR-004, SC-001. |
| TM-06 | Model output supplies extra state fields, malicious serialization or oversized payloads. | Providers and persistence use closed typed schemas, payload limits and version checks; no arbitrary-object deserialization. | Five malformed-output cases plus stale-state tests; FR-012, SC-003/007. |
| TM-07 | Retry or racing workers duplicate a response or overwrite a turn. | Persistence enforces request uniqueness, digests, revision checks and fenced leases; commit is separate from external computation. | Crash-window and concurrency suite; FR-007–009, SC-002. |
| TM-08 | Forged, stale or replayed resume bypasses a pause. | Service validates owner, pause ID and revision; persistence consumes pause once and returns same-key results. | Five resume-tampering cases and escalation lifecycle; FR-011, SC-003/004. |
| TM-09 | Secrets or customer bodies leak through traces, errors or nested provider spans. | Observability exports allow-listed metadata only; service sanitizes errors; raw automatic tracing disabled. | Seed canaries and inspect actual exporter payloads including failures; FR-012/014, SC-006. |
| TM-10 | Oversized input or retries cause unbounded cost/work. | Service limits messages and conversation length; worker persists two-attempt/60-second budget and caps concurrency. | Limit edges, timeouts, restart budget exhaustion; FR-013/015, SC-007. |
| TM-11 | Deleted/expired state survives in checkpoint tables or is recreated by a worker. | Persistence blocks access, revokes leases and purges all related records; commits require an extant authorized conversation. | Controlled-time purge plus in-flight completion test; FR-016, SC-007. |
| TM-12 | Source changes or linked paths substitute unreviewed content after indexing. | Knowledge validates path identity and source hashes against the pinned manifest; rejects drift and mixed corpus versions. | Linked/escaping path, changed hash and stale-manifest cases; FR-003/004, SC-001/007. |
| TM-13 | Escalation is falsely reported as delivered or automation continues after pause. | Conversations commit pending state and truthful response together; no specialist execution while pending. | Six handoff-boundary cases; FR-010/011, SC-004. |

Test fixtures for these attacks are project-authored synthetic artifacts. No attack instruction
changes authorization or permits accessing third-party systems. SC-003 defines a minimum set, not a
complete inventory of all regression tests needed for this register.

## Future Integration Obligations

| ID | Applies when | Required design and evidence |
| --- | --- | --- |
| TM-14 | Chatwoot integration | Verify webhook authentication supported by chosen deployment; validate account/inbox binding, origin and event type; deduplicate and reconcile reordered events; exclude outgoing-message loops. |
| TM-15 | Human ownership | Persist outbound handoff intent, reconcile timeout ambiguity, suppress bot replies during transition and human ownership; require authorized return-to-bot evidence. Test races with human replies. |
| TM-16 | Banking tools | Recheck verified actor, resource ownership, allow-listed operation, policy and action-specific approval at execution; idempotent mutation ledger; never trust model approval claims. |
| TM-17 | Public/container deployment | TLS ingress, managed secrets, authentication lifecycle, per-owner throttling, network restrictions, dependency/image review, migrations/backups and restore tests. |
| TM-18 | Official evaluation | Separate task/answer/reward access from runtime, freeze configuration and held-out set, prevent reference-action leakage, report comparable baselines and actual policy failures. |

These future controls are tracked obligations, not controls claimed by Feature 002. Each subsequent
specification must promote applicable rows into testable requirements before integration.

## Residual Risk and Review Triggers

Prompt separation and citation validation do not prove resistance to all prompt injection or semantic
hallucinations. Frozen tests provide bounded evidence and require manual review of failed and
unsupported answers. Providers receive selected synthetic conversation/evidence content; metadata
redaction in tracing does not remove content from model requests. Choose provider data handling
deliberately before any real-data scope change.

Interrupted model calls may be billed twice even when only one answer is committed. A single local
database is not a high-availability deployment. The initial retention policy excludes retained
backups and real-user data; public deployment must revisit erasure across backups and external systems.
Opaque demo tokens do not establish banking identity. Human handoff is unavailable until its adapter
is implemented and verified.

Revisit this model when adding any tool, data source, provider, external inbox, state migration,
public ingress or broader retention. Package owners own controls; implementation review must link
each applicable row to concrete test evidence. No row is marked mitigated solely because this
document describes a defense.

## Feature 002 implementation

Local evidence now includes guarded native checkpoints, owner-isolated resume, atomic purge rollback, explicit metadata-only export and a thirty-case offline adversarial inventory. Deterministic injection tests do not establish live-model resistance. Trace delivery is best effort; exported metadata follows external retention. Hosted/live evidence remains pending.
