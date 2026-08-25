<!--
Sync Impact Report
- Version change: unratified template -> 1.0.0
- Modified principles:
  - Template principle slot 1 -> I. Module Documentation Is Mandatory
  - Template principle slot 2 -> II. File-Level Documentation Is Mandatory
  - Template principle slot 3 -> III. Code Interfaces and Decisions Are Documented
  - Template principle slot 4 -> IV. Strict Typing Is Non-Negotiable
  - Template principle slot 5 -> V. Formatting and Quality Gates Are Automated
- Added sections:
  - Documentation and Code Quality Standards
  - Development Workflow and Quality Gates
- Removed sections: none
- Follow-up TODOs: none
-->

# VerityCX Constitution

## Core Principles

### I. Module Documentation Is Mandatory

Every maintained module MUST contain a `README.md` at its root. A module is any
independently deployable, importable, executable, or responsibility-bounded package or
component. Its README MUST state the module's purpose, responsibilities, boundaries,
directory structure, public interfaces, dependencies, configuration, usage, and test
instructions. It MUST also identify important operational constraints and failure modes
when they exist. A change that alters any documented behavior MUST update the README in
the same change set. This rule ensures that a contributor can understand and use a module
without reverse-engineering its implementation.

### II. File-Level Documentation Is Mandatory

Every maintained source-code file MUST begin with a language-appropriate file-level or
module-level documentation comment that explains its purpose, primary responsibilities,
and any important dependencies or invariants. Every other maintained text file MUST have
an equivalent leading comment only when its format officially supports comments and the
established conventions for that format permit them. Unsupported syntax, dummy fields,
encoded comments, and other workarounds MUST NOT be used to simulate comments. Generated,
vendored, binary, lock, and other non-commentable files are exempt. This rule makes file
intent discoverable while preserving valid, conventional file formats.

### III. Code Interfaces and Decisions Are Documented

Every function, method, and class MUST have a language-supported docstring or documentation
comment. The documentation MUST describe purpose and behavior and, where applicable,
inputs, outputs, raised errors, state changes, side effects, and security or authorization
expectations. Maintained code MUST use inline or block comments to explain non-obvious
algorithms, invariants, policy decisions, risk controls, and multi-step operations.
Comments MUST explain intent or rationale instead of restating syntax, and artificial
comments MUST NOT be added merely to satisfy a count. Documentation MUST be updated in the
same change set as the behavior it describes. This rule keeps interfaces usable and makes
consequential implementation decisions reviewable.

### IV. Strict Typing Is Non-Negotiable

All maintained code MUST use the strongest practical strict-typing mode supported by its
language and approved project toolchain. Function and method parameters, return values,
class fields, shared state, public contracts, tool payloads, and persistence boundaries
MUST have explicit types. Unbounded dynamic types, unchecked casts, ignored diagnostics,
and equivalent type-safety escape hatches MUST NOT be used without a narrow, documented,
and reviewer-approved justification. External or untyped data MUST be validated at the
boundary before entering typed application state. The repository's strict type checker
MUST pass before a change is merged. This rule prevents ambiguous contracts and catches
integration defects before runtime.

### V. Formatting and Quality Gates Are Automated

All maintained code and supported documentation MUST be formatted by the repository's
approved, deterministically configured formatter. Contributors MUST NOT introduce local
formatting conventions that conflict with repository configuration. Continuous integration
MUST verify formatting without rewriting files, run strict type checks, and run configured
documentation or lint checks. A change MUST NOT merge while any required quality gate
fails. This rule makes style reproducible and turns documentation, typing, and formatting
requirements into enforceable engineering controls.

## Documentation and Code Quality Standards

- A maintained file is a project-owned file that contributors are expected to edit.
  Generated artifacts, third-party or vendored content, binary assets, and dependency lock
  files are outside that definition unless the project explicitly assumes ownership of them.
- A module README MUST be useful on its own. Links to deeper documentation MAY supplement it
  but MUST NOT replace the required purpose, interface, setup, usage, and testing information.
- File-level comments and docstrings MUST use the official syntax and established conventions
  of the file's language or format. Files that do not support comments MUST remain valid and
  unmodified for this purpose; their context MUST be documented in the nearest module README.
- Documentation MUST be specific enough to be checked against the implementation. Vague or
  stale descriptions are defects and MUST be corrected when discovered.
- Type-checker, formatter, documentation, and lint configurations MUST be version-controlled
  so local development and continuous integration apply the same rules.

## Development Workflow and Quality Gates

Every specification and implementation plan MUST identify the modules and public contracts
affected by the work. Before review, contributors MUST run the configured formatter, strict
type checker, documentation checks, and relevant tests. Pull-request review MUST verify that:

1. Every new or changed module has an accurate `README.md`.
2. Every new or changed applicable file has a meaningful file-level comment.
3. Every new or changed function, method, and class has accurate documentation.
4. Non-obvious logic and consequential decisions have explanatory inline or block comments.
5. New and changed contracts are explicitly typed and untyped inputs are validated.
6. Formatting, typing, documentation, lint, and test gates pass without manual exceptions.

Violations in code touched by a change MUST be corrected before merge. A temporary exception
is permitted only when compliance is technically blocked: it MUST be narrowly scoped,
documented with the reason and remediation owner, approved during review, and assigned an
expiry date or tracked remediation issue.

## Governance

This constitution is the authoritative source for VerityCX documentation, typing, and
formatting policy. When another project document conflicts with it, this constitution takes
precedence. Amendments MUST be proposed in a reviewed change that states the rationale,
compatibility impact, required migration, and semantic version change.

Constitution versions follow semantic versioning: MAJOR for removal or incompatible
redefinition of a principle, MINOR for a new principle or materially expanded obligation,
and PATCH for non-semantic clarification. Every amendment MUST update the Sync Impact Report,
version, and last-amended date. The ratification date MUST remain the original adoption date.

Specifications, plans, task lists, code reviews, and release checks MUST demonstrate
compliance with applicable principles. Reviewers MUST reject unexplained violations. The
team MUST review this constitution when project tooling or development workflows change and
at least once before each production release.

**Version**: 1.0.0 | **Ratified**: 2026-08-25 | **Last Amended**: 2026-08-25
