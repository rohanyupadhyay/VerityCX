# Feature Specification: Symphony Plus Installation Smoke Test

**Feature Branch**: `symphony/gh-7-installation-smoke-test`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Exercise the installed Spec Kit workflow through specification approval only. Do not implement production behavior. This issue will be cancelled after checkpoint and restart-recovery verification."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reach a Durable Specification Gate (Priority: P1)

As a workflow operator, I want a newly labeled issue to advance through specification and clarification into a durable specification-approval checkpoint so that I can verify the installed workflow and its restart-recovery behavior without changing production behavior.

**Why this priority**: Reaching and preserving the approval gate is the sole purpose of this smoke test. It proves the workflow can create reviewable artifacts, publish them, and pause safely for human approval.

**Independent Test**: Start from issue 7 with no prior workflow checkpoint, run the specification workflow, and confirm that the issue pauses at a specification approval checkpoint referencing the published issue branch and exact commit.

**Acceptance Scenarios**:

1. **Given** issue 7 is open, labeled for workflow execution, and has no prior checkpoint, **When** the specification phase completes without material ambiguities, **Then** the specification and its quality checklist are committed and published on the dedicated issue branch.
2. **Given** the published specification passes its quality checklist, **When** the workflow records its checkpoint, **Then** the checkpoint requests specification approval, identifies the specification phase and gate, and records the exact published branch and commit.
3. **Given** the workflow is restarted after the approval checkpoint, **When** it reads the durable issue and checkpoint state, **Then** it remains paused at specification approval and does not repeat completed specification work or begin planning.

### Edge Cases

- If an existing issue branch or feature directory is discovered, the workflow reuses it rather than creating a competing branch or duplicate artifact set.
- If a material specification ambiguity is discovered, the workflow records an input checkpoint with a precise question and stops instead of assuming an answer.
- If artifact publication or checkpoint creation fails, the workflow reports the exact failure and does not claim that the specification gate was reached.
- General or duplicate issue comments that are not normalized workflow triggers do not advance the phase.
- An approval, planning, task-generation, implementation, or pull-request action is outside this smoke test unless a later authorized workflow trigger explicitly expands the scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow MUST use one dedicated issue branch named `symphony/gh-7-installation-smoke-test` for all smoke-test artifacts.
- **FR-002**: The workflow MUST use `specs/gh-7-installation-smoke-test` as the single feature directory and persist that selection for restart recovery.
- **FR-003**: The workflow MUST create a specification that describes the smoke-test goal, boundaries, acceptance scenarios, failure cases, and measurable completion outcomes.
- **FR-004**: The workflow MUST validate the specification with the installed specification-quality checklist and resolve every failing item before publication, except for a documented unresolved item that requires human input.
- **FR-005**: The workflow MUST request human input through a durable issue checkpoint if a material ambiguity cannot be resolved from the authorized issue context.
- **FR-006**: The workflow MUST commit and publish all specification artifacts before creating the specification-approval checkpoint.
- **FR-007**: The specification-approval checkpoint MUST identify the `specify` phase, the `spec` gate, the published branch, and the exact 40-character commit identifier.
- **FR-008**: The checkpoint summary MUST link the specification and state the validation performed so a reviewer can make an approval decision from durable repository and issue state.
- **FR-009**: A restarted workflow MUST recognize the published specification checkpoint as completed work and remain paused pending a normalized approval, revision, status, or cancellation trigger.
- **FR-010**: The workflow MUST NOT create production behavior, planning artifacts, task artifacts, implementation changes, or a pull request as part of this smoke test.
- **FR-011**: The specification MUST identify affected modules and public contracts; for this workflow-only smoke test, both MUST be explicitly recorded as none.

### Scope and Boundaries

- **In scope**: Issue-state inspection, dedicated branch creation or reuse, specification creation, specification-quality validation, artifact publication, and creation of a durable specification-approval checkpoint.
- **Out of scope**: Planning, custom checklist generation, task generation, cross-artifact analysis, application-code changes, tests of production behavior, implementation, pull-request creation, and merge.
- **Affected modules**: None. This smoke test changes only Spec Kit workflow artifacts.
- **Affected public contracts**: None. No application or integration contract is introduced or changed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Exactly one dedicated issue branch and one feature directory contain the smoke-test specification artifacts.
- **SC-002**: The specification-quality checklist has 16 of 16 items passing before the artifacts are published.
- **SC-003**: The published checkpoint records a branch and 40-character commit identifier that resolve to the committed specification and checklist.
- **SC-004**: After checkpoint creation, zero planning, task, production-code, implementation, or pull-request artifacts have been created for this issue.
- **SC-005**: On restart, the workflow can determine from durable state alone that the next permitted action is a human decision at the specification gate.

## Assumptions

- The installed Spec Kit templates, scripts, GitHub integration, and workflow checkpoint service are available in the isolated issue workspace.
- Issue 7 and its authorized workflow-control state are the durable source of truth for this smoke test.
- No clarification is required when the issue instructions, repository constitution, and current artifacts together provide a single unambiguous course of action.
- The issue will be cancelled by a later normalized trigger after checkpoint and restart-recovery verification; cancellation is not part of the current specification phase.
