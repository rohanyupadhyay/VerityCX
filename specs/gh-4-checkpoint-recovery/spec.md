# Feature Specification: Document Checkpoint Recovery

**Feature Branch**: `symphony/gh-4-checkpoint-recovery`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Create a documentation-only specification for adding a short checkpoint-recovery note to the Symphony operator guide. It must explain that GitHub issue comments hold durable workflow state and that restarting Symphony must not repeat completed phases."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover Without Repeating Work (Priority: P1)

As a Symphony operator, I want the operator guide to explain where durable workflow state is kept and how restart recovery behaves so that I can restart Symphony without expecting completed phases to run again.

**Why this priority**: Correct restart expectations prevent duplicate workflow work and make GitHub the understandable source of durable state for operators.

**Independent Test**: A reviewer can read only the checkpoint-recovery note and correctly identify both the durable state location and the required behavior after a restart.

**Acceptance Scenarios**:

1. **Given** an operator is reading the Symphony operator guide, **When** the operator reads the checkpoint-recovery note, **Then** the operator can identify GitHub issue comments as the durable store for workflow state.
1. **Given** a workflow has completed one or more phases before Symphony restarts, **When** the operator reads the checkpoint-recovery note, **Then** the operator understands that Symphony resumes from durable state and does not repeat completed phases.

### Edge Cases

- The note must not imply that the local dashboard or an in-memory process is the durable source of workflow state.
- The note must distinguish recovery from a retry: a restart alone does not authorize repeating a completed phase.
- The note must remain accurate when the current process or local runtime state is unavailable, because GitHub issue comments are the durable source.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Symphony operator guide MUST contain a short checkpoint-recovery note.
- **FR-002**: The note MUST state that GitHub issue comments hold durable workflow state.
- **FR-003**: The note MUST state that, after Symphony restarts, recovery uses the durable workflow state recorded in GitHub issue comments.
- **FR-004**: The note MUST state that restarting Symphony does not repeat workflow phases already recorded as completed.
- **FR-005**: The note MUST use operator-facing language that can be understood without knowledge of Symphony's internal implementation.
- **FR-006**: The note MUST remain limited to checkpoint recovery and MUST NOT introduce new workflow behavior, runtime configuration, or implementation instructions.

### Affected Module and Public Contracts

- **Affected module**: The maintained documentation module under `docs/`, specifically the Symphony operator guide identified by `docs/README.md`.
- **Public contracts**: No application API, command, configuration, or other public software contract changes. The note clarifies the documented operational contract for restart recovery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a documentation review, 100% of reviewers can identify GitHub issue comments as the durable workflow-state location from the note alone.
- **SC-002**: In a documentation review, 100% of reviewers can state that a Symphony restart must not repeat completed workflow phases after reading the note.
- **SC-003**: The note communicates both required recovery facts in one concise passage without requiring readers to consult implementation details.
- **SC-004**: Review finds zero claims that assign durable workflow state to the local dashboard, process memory, or another non-GitHub location.

## Assumptions

- `docs/symphony.md` remains the operator guide identified by the documentation module README.
- Existing terminology such as "workflow phase," "GitHub issue comment," and "restart" is retained for consistency with the guide.
- This feature specifies a documentation clarification only; no runtime behavior, code, tests, configuration, planning artifacts, or implementation changes are in scope.
- The issue will be cancelled and closed after checkpoint status recovery is verified, as stated in the issue acceptance criteria.
