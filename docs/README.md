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
- [Local Chatwoot setup](chatwoot-local-setup.md): owned local provisioning, private
  credentials, network requirements and actual widget/inbox acceptance gates.
- [Symphony Plus operator guide](../.symphony-plus/README.md): GitHub issue-driven automation.
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

The [customer chat design](superpowers/specs/2026-10-26-customer-chat-design.md) and
[implementation plan](superpowers/plans/2026-10-26-customer-chat.md) record the branded
page, native widget, signed bridge and open live deployment/AI acceptance gates.

The approved [bank information design](superpowers/specs/2026-10-29-bank-information-design.md)
and [implementation plan](superpowers/plans/2026-10-29-bank-information.md) document
the implemented service pages, complete policies, shared search, and contextual
VerityCX entry points under `/bank`. Content comes from the active approved corpus;
missing bank facts remain absent. Public browsing works independently of chat.
