<!-- Explains ownership and use of durable knowledge-support planning artifacts. -->

# Durable Knowledge-Support Workflow

This directory owns Feature 002 requirements, not an implemented runtime. Its boundary is a grounded,
durable knowledge conversation with a truthful pending escalation record.

## Structure and Interfaces

- [spec.md](spec.md): user stories, requirements, entities and acceptance outcomes.
- [plan.md](plan.md): implementation approach, constitution gates and source responsibilities.
- [tasks.md](tasks.md): dependency-ordered implementation and acceptance tasks grouped by user story.
- [research.md](research.md): selected dependencies and evidence-backed technical decisions.
- [data-model.md](data-model.md): entities, constraints and state transitions.
- [contracts](contracts/README.md): HTTP, execution, source/provider and configuration contracts.
- [quickstart.md](quickstart.md): post-implementation setup, validation and release evidence.
- [checklists/requirements.md](checklists/requirements.md): specification-quality validation; checked items do not establish implementation completion.
- [Platform design](../../docs/platform-design.md): proposed modules and technical contracts.
- [Threat model](../../docs/threat-model.md): risks, controls and residual limitations.
- [Roadmap](../../docs/platform-roadmap.md): delivery sequence and foundation dependencies.

## Configuration, Usage and Verification

Run commands from the Git root. `.specify/feature.json` selects this feature independently of branch
name. The plan and task list are available for `speckit-analyze` consistency review before implementation.
Feature 001 artifacts retain their separate authority.

```text
uv run mdformat --check specs/002-durable-knowledge-support
```

Documentation uses the locked development environment and requires no service credentials.
Unresolved requirements, misleading handoff claims, broken links and confusion between document
quality and runtime evidence are review failures. The generated tasks are initially unchecked and do
not establish runtime implementation; future commands in the quickstart are explicitly labeled.
