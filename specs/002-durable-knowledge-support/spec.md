<!-- Defines requirements and acceptance boundaries for durable knowledge support. -->

# Feature Specification: Durable Knowledge-Support Workflow

**Feature Branch**: Not created; authored on `main`. Feature directory is independent of branch name.

**Created**: 2026-09-12

**Status**: Locally implemented; hosted and human-reviewed live acceptance remain pending

**Input**: User-approved next increment: a customer asks a banking-policy question, receives a grounded answer, continues after a service restart, and can request escalation. Establish typed conversation, policy, provider and persistence boundaries for the future multi-agent platform.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive a grounded policy answer (Priority: P1)

A demo customer asks a general banking-product or policy question and receives an answer supported by approved documents. Unsupported questions receive an honest limitation or clarification request.

**Why this priority**: Attributable knowledge support is the smallest useful customer-facing capability.

**Independent Test**: Use project-authored synthetic documents and questions to verify answers, citations and abstention without account tools or a human-support integration.

**Acceptance Scenarios**:

1. **Given** an authorized demo customer and relevant approved documents, **When** a supported question is submitted, **Then** the answer identifies a supporting document and section for each substantive policy claim.
1. **Given** missing or contradictory evidence, **When** a question is submitted, **Then** the system explains the limitation or requests clarification without inventing policy.
1. **Given** a request to change an account or dispute a transaction, **When** submitted, **Then** execution is reported unavailable and escalation is recorded only if requested; no banking records are read or changed.
1. **Given** instructions in a retrieved document or customer message requesting privileged behavior, **When** processed, **Then** they cannot expand source access, authorize tools, change identity or expose protected conversation data.

### User Story 2 - Continue reliably after interruption (Priority: P2)

A returning demo customer continues the same conversation after a restart or transient failure without losing accepted messages or receiving duplicate committed answers.

**Why this priority**: Continuity distinguishes the workflow from a one-shot chatbot.

**Independent Test**: Use a deterministic response substitute, restart at defined boundaries and resubmit the same request identifiers.

**Acceptance Scenarios**:

1. **Given** an accepted turn, **When** the service restarts before or after producing its answer, **Then** the conversation can be recovered and the accepted message appears once.
1. **Given** a committed answer whose delivery was interrupted, **When** the customer retries the same request, **Then** the same committed answer is returned without creating another turn.
1. **Given** simultaneous submissions to one conversation, **When** processed, **Then** one advances the conversation and the other receives an explicit retryable conflict; no turn silently overwrites another.
1. **Given** unavailable durable storage, **When** a message is submitted, **Then** temporary unavailability is reported and the system does not claim acceptance.
1. **Given** another customer's identifier or a stale resume request, **When** access is attempted, **Then** access or resumption is denied without exposing protected content or changing state.

### User Story 3 - Request escalation without losing context (Priority: P3)

A customer asks for a human. The system saves the reason and context and pauses automated answers, clearly explaining that this increment has no connected human-support inbox.

**Why this priority**: Establish truthful escalation and a durable handoff boundary before connecting an external inbox.

**Independent Test**: Without a support platform, request escalation, restart the service and inspect escalation status.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** the customer explicitly requests a human, **Then** an escalation record and factual summary are saved and the customer is told that the request is recorded but no human has been notified.
1. **Given** a pending escalation, **When** another message is submitted, **Then** it is retained, pending status is returned and no specialist answer is generated.
1. **Given** a pending escalation, **When** the authenticated owner explicitly chooses to continue automated support using the current pause identifier, **Then** automation resumes once with preserved context.
1. **Given** a duplicate escalation or resume request, **When** retried, **Then** the existing result is returned without duplicate records or transitions.

### Edge Cases

- Empty, malformed, oversized or over-limit input is rejected before model execution with a stable reason and no partial turn.
- Unavailable sources, invalid citations and incompatible corpus versions cause abstention or a recoverable error, never invented citations.
- Provider timeout, rate limiting or malformed output produces bounded failure and a retry path; raw diagnostics and credentials are not returned.
- Reusing a request identifier with different content is rejected; identifiers cannot retrieve another owner's response.
- An unsupported stored state version fails closed instead of being silently discarded or treated as a new conversation.
- Expired or deleted conversations cannot be resurrected by retry, resume or delayed processing.
- Optional trace-export failure does not block a response once required local audit and state records are saved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST authorize a server-recognized demo identity for every create, submit, read, escalation, resume and delete operation; a conversation identifier alone MUST NOT confer access.
- **FR-002**: The system MUST distinguish knowledge questions, clarification needs, unavailable account/transaction operations and explicit human requests. Only knowledge questions may enter the knowledge-answering workflow.
- **FR-003**: Answers MUST use only validated, pinned, application-eligible documents. Runtime consumers MUST reject evaluation tasks, expected answers, grading data, unclassified upstream paths and arbitrary customer-supplied source locations before loading them.
- **FR-004**: Each substantive policy claim MUST identify an approved document and section used for that answer. Missing, conflicting or insufficient evidence MUST produce clarification or abstention. Citation validity alone MUST NOT count as grounding quality.
- **FR-005**: Customer messages, retrieved documents and provider output MUST remain untrusted content; none may modify authorization, allowed capabilities, source permissions or human-ownership state.
- **FR-006**: This feature MUST NOT read customer banking records, execute account or transaction operations, or claim those operations succeeded.
- **FR-007**: Accepted messages, committed responses, source references, workflow status and escalation state MUST survive restart. Acceptance MUST be acknowledged only after durable recording.
- **FR-008**: Requests MUST have an owner-scoped unique identifier. Identical retries MUST reuse the durable result; conflicting reuse MUST fail. Concurrent changes MUST serialize or report a retryable conflict without lost updates.
- **FR-009**: Recovery MUST resume from saved progress and expose at most one committed response per accepted turn. Interrupted external computation may repeat, but duplicate committed turns MUST NOT result.
- **FR-010**: Escalation MUST durably record reason, factual summary, source references and workflow status, pause specialist answers and disclose that human delivery is unavailable in this feature.
- **FR-011**: Resumption MUST require the authorized owner, explicit intent to continue automation and the current unconsumed pause identifier. Duplicate identical requests MUST reuse their result; stale or foreign requests MUST fail.
- **FR-012**: The system MUST validate external and stored inputs against explicit contracts, reject unsupported state versions and expose categorized errors without secrets or raw diagnostics.
- **FR-013**: Provider execution MUST be bounded to two attempts per turn within a 60-second processing deadline. Exhaustion MUST produce a durable failure; a new turn may retry the question, while retrying the original identifier returns its existing failure. Recovery MUST preserve attempt count and deadline.
- **FR-014**: Every accepted turn MUST have an audit record with correlation identifier, outcome, route, source identifiers, elapsed time and failure category when applicable. Secrets and message/document bodies MUST be excluded from exported traces by default. Optional export failure MUST NOT block operation.
- **FR-015**: The demo MUST accept at most 8,000 characters per message and 100 customer messages per conversation. Excess input MUST be rejected clearly before external processing.
- **FR-016**: Conversation content, checkpoints, deduplication records and local audit records MUST expire 30 days after last accepted activity, with removal within 24 hours of expiry. Authorized deletion MUST block access immediately and remove these records within 24 hours; unfinished work MUST NOT repopulate them. Exported metadata MUST contain no conversation bodies or stable customer identity.
- **FR-017**: The feature MUST provide a documented customer-facing service interface for these operations and distinguish an alive process from a service ready to accept durable work.
- **FR-018**: Control-flow correctness and security regression tests MUST run with project-authored synthetic fixtures and a deterministic provider substitute without paid credentials. Live grounding acceptance and a separate opt-in demonstration MUST record provider/model configuration, corpus version and outcomes without committing upstream content or secrets. Deterministic results MUST NOT be reported as live-model grounding evidence.

### Key Entities

- **Demo identity**: Server-recognized conversation owner; not banking identity verification.
- **Conversation**: Owner, identifier, state version, ordered turns, workflow status, revision and expiry.
- **Turn**: Request identifier, customer message, processing status, attempt budget and one optional committed response.
- **Evidence reference**: Approved corpus revision, document identifier, section identifier and passage provenance.
- **Escalation**: Reason, factual summary, conversation revision, pause identifier and pending/cancelled status; no external delivery claim.
- **Audit record**: Sanitized operational outcome and correlation metadata, distinct from customer content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Using the selected live provider on 40 frozen project-authored questions and synthetic documents (20 supported, 10 unsupported, 10 ambiguous/conflicting), at least 18 supported questions receive fully supported answers; all unsupported questions abstain and all ambiguous/conflicting questions clarify or disclose conflict. A human reviewer checks each policy claim against fixture sources and records the rubric and result. This opt-in run is feature acceptance, not a benchmark score; offline substitutes do not satisfy it. [FR-002–FR-004]
- **SC-002**: All 20 restart/retry/concurrency cases preserve every accepted message and produce no duplicate committed answer: restart after acceptance, before response commit, after commit before delivery, repeated request and concurrent submission, each exercised four times. [FR-007–FR-009]
- **SC-003**: All 30 adversarial cases prevent unauthorized access, privileged state changes and unsupported operations: five cases each for customer injection, document injection, cross-owner access, forbidden sources, resume tampering and malformed provider output. Passing this set is bounded evidence, not universal injection resistance. [FR-001, FR-003, FR-005, FR-006, FR-011, FR-012]
- **SC-004**: All six escalation cases (request, duplicate, restart, subsequent message, valid resume, stale resume) preserve context and report delivery status truthfully. [FR-010, FR-011]
- **SC-005**: In a recorded local run with a deterministic substitute, 10 simultaneous conversations each complete three turns; at least 95% of turns finish within five seconds, with zero cross-conversation leakage. Live-provider latency, cost and failure rate are reported separately without inheriting this target. [FR-007–FR-009, FR-013]
- **SC-006**: Every accepted turn in the acceptance suite has required audit fields; seeded secret/body canaries are absent from trace-export payloads and user-visible errors. [FR-012, FR-014]
- **SC-007**: Boundary cases at and above both input limits, storage-unavailable acceptance, stale state version, provider timeout and deletion/expiry pass with specified outcomes. Deletion and expiry use controlled time and a concurrent unfinished turn. [FR-012–FR-017]
- **SC-008**: The offline suite succeeds without credentials, and one opt-in live run demonstrates a grounded answer, follow-up after restart and truthful escalation with sanitized evidence. [FR-018]

## Assumptions

- English-language, single-organization, local portfolio demo with synthetic identities. Public hosting, real customers, banking verification and regulatory certification are outside this feature.
- Feature 001 remains acquisition and inspection only. Its recorded open acceptance tasks are tracked independently and must be resolved before a release claim relying on that foundation; Feature 002 design can proceed meanwhile.
- Only the approved documents are consumed here. Banking database access, embeddings/vector infrastructure, operational specialists, external human delivery, container deployment and official benchmark evaluation belong to later features.
- One live provider and a deterministic substitute suffice initially. Credentials, exact model and package pins are implementation-plan decisions, not specification prerequisites.
- Retention and input/attempt limits are explicit initial product defaults, not legal requirements.
- A later human-support feature replaces pending escalation with delivery and human ownership; this increment never labels a request delivered.
- Affected responsibilities: service boundary, orchestration, knowledge access, policy, provider adaptation, durable storage and sanitized observability. Technical contracts and proposed modules are in the [platform design](../../docs/platform-design.md); controls are in the [threat model](../../docs/threat-model.md).
