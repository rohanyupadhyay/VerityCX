<!-- Describes maintained project documentation and its verification boundary. -->

# Documentation

This directory owns current data-use guidance and separately labeled future platform planning.
It defines no application API or runtime configuration.

## Structure and Authority

- `data/tau3-banking.md`: current acquisition, provenance, inspection, and default-deny data policy.
- `project-vision.md`: the original future platform vision, not current implementation status.
- `platform-roadmap.md`: proposed delivery sequence and foundation acceptance dependencies.
- `platform-design.md`: proposed architecture, module boundaries and technical contracts.
- `threat-model.md`: initial trust boundaries, required controls and residual risks.
- `symphony.md`: operator guide for GitHub issue-driven Symphony and Spec Kit automation.
- [Root README](../README.md): canonical developer commands and implemented scope.
- [Spec Kit feature](../specs/001-acquire-tau3-banking/spec.md): requirements and acceptance authority.
- [Feature 002](../specs/002-durable-knowledge-support/spec.md): durable knowledge-support requirements and acceptance scope.
- [Feature 002 plan](../specs/002-durable-knowledge-support/plan.md): research, data model, contracts and post-implementation validation guide.

All project commands run from the Git repository root. Relative Markdown links are resolved from
their containing document. Keep current instructions aligned with the constitution, source, and
CI; dated audit records retain historical paths without becoming current instructions.

## Dependencies, Usage, and Verification

Documentation needs no runtime dependency. Formatting uses the locked development environment and
the root `pyproject.toml` mdformat configuration:

```text
uv run mdformat --check docs
```

The [quickstart](../specs/001-acquire-tau3-banking/quickstart.md) lists the complete quality gates.
Stale commands, broken relative links, ambiguous implementation claims, and incorrect data-use
classification are documentation failures; formatting alone does not establish their correctness.

## Feature 002 implementation

Feature 002 implementation and local evidence are documented in `specs/002-durable-knowledge-support/quickstart.md`. Hosted and human-reviewed live gates remain open.
