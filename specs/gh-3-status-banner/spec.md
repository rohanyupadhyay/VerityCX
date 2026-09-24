# Feature Specification: Temporary Workflow Status Banner

**Feature Branch**: `symphony/gh-3-status-banner`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Add a temporary operator status banner to the Symphony guide stating that GitHub issues are the workflow UI. Keep the change documentation-only, require no application-code or database changes, and make the banner accessible to screen readers."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recognize the workflow interface (Priority: P1)

As a Symphony operator reading the guide, I need a prominent temporary status banner that tells me GitHub issues are the workflow UI so that I use the correct place to observe and control workflow progress.

**Why this priority**: The smoke test succeeds only if operators receive the intended workflow-control message without mistaking an application interface for the source of workflow state.

**Independent Test**: Review the Symphony guide as both a sighted reader and through its text/semantic representation. The banner independently delivers the exact workflow message, is encountered as guide content, and remains understandable without relying on visual styling.

**Acceptance Scenarios**:

1. **Given** an operator opens the Symphony guide, **When** they reach the temporary status banner, **Then** it states that "GitHub issues are the workflow UI."
1. **Given** an operator uses a screen reader or other text-based assistive technology, **When** the guide content is read in document order, **Then** the complete banner message is announced as meaningful text.
1. **Given** visual styling, color, or decorative imagery is unavailable, **When** an operator reads the guide, **Then** the banner's status and message remain understandable from text alone.

### Edge Cases

- If guide styling does not load or is stripped, the banner must retain its full meaning and temporary-status label as plain text.
- If a screen reader ignores decorative presentation, the complete banner message must still appear in the document's reading order without duplicated or conflicting announcements.
- If other workflow guidance appears nearby, it must not contradict the banner's statement that GitHub issues are the workflow UI.
- The banner must be identifiable as temporary so it is not mistaken for permanent product behavior after the workflow-control smoke test ends.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Symphony guide MUST contain one temporary operator status banner in the guide's introductory workflow context.
- **FR-002**: The banner MUST include the exact sentence: "GitHub issues are the workflow UI."
- **FR-003**: The banner MUST identify itself in text as temporary status information.
- **FR-004**: The complete banner message MUST be available as meaningful text in the document's normal reading order so screen readers can announce it.
- **FR-005**: The banner MUST remain understandable without color, images, icons, or other visual styling, and decorative content MUST NOT duplicate or obscure the announced message.
- **FR-006**: The feature MUST be limited to maintained documentation and MUST NOT require application-code, runtime-configuration, or database changes.
- **FR-007**: The banner MUST NOT introduce a new workflow interface, persistence behavior, user permission, or public application contract.
- **FR-008**: The specification and any eventual documentation change MUST treat the banner as scoped to the workflow-control smoke test and suitable for removal after checkpoint recovery is verified.

### Scope and Affected Documentation

- **Affected module**: Repository-level Symphony workflow documentation.
- **Affected maintained document**: The Symphony guide in `WORKFLOW.md`.
- **Public contracts**: None; the banner documents the existing operator workflow and does not change application behavior or interfaces.
- **Out of scope**: Application source files, tests for application behavior, database schemas or migrations, workflow automation behavior, GitHub issue state changes beyond the durable review workflow, and implementation during the specification checkpoint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The banner contains the required sentence exactly once and 100% of reviewers can identify GitHub issues as the workflow UI from the banner alone.
- **SC-002**: A screen-reader-oriented inspection finds 100% of the banner's meaningful words in document reading order, with no meaning conveyed solely by color, imagery, or icons.
- **SC-003**: A documentation-scope review finds zero application-code, runtime-configuration, database-schema, or migration changes required by the feature.
- **SC-004**: The banner is explicitly labeled as temporary and its relationship to the workflow-control smoke test can be identified without consulting application behavior.
- **SC-005**: All acceptance scenarios can be evaluated by reviewing the Symphony guide alone.

## Assumptions

- `WORKFLOW.md` is the repository's maintained Symphony guide and is the sole eventual content target.
- Operators include people who use screen readers or text-only document views.
- Native document text and heading/paragraph reading order provide the accessibility baseline; visual prominence may supplement but cannot replace that text.
- Removal of the temporary banner is a later, explicitly authorized documentation action after checkpoint recovery verification and is not part of this specification-only smoke-test phase.
- No new data is created, stored, or transmitted by this documentation-only feature.
