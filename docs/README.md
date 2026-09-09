<!-- Describes maintained project documentation and its verification boundary. -->

# Documentation

This directory owns current data-use guidance and the separately labeled future platform vision.
It defines no application API or runtime configuration.

## Structure and Authority

- `data/tau3-banking.md`: current acquisition, provenance, inspection, and default-deny data policy.
- `project-vision.md`: the original future platform vision, not current implementation status.
- [Root README](../README.md): canonical developer commands and implemented scope.
- [Spec Kit feature](../specs/001-acquire-tau3-banking/spec.md): requirements and acceptance authority.

All project commands run from the Git repository root. Relative Markdown links are resolved from
their containing document. Keep current instructions aligned with the constitution, source, and
CI; dated audit records retain historical paths without becoming current instructions.

## Dependencies, Usage, and Verification

Documentation needs no runtime dependency. Formatting uses the locked development environment and
the root `pyproject.toml` mdformat configuration:

```text
uv run mdformat --check docs/README.md docs/project-vision.md docs/data/tau3-banking.md
```

The [quickstart](../specs/001-acquire-tau3-banking/quickstart.md) lists the complete quality gates.
Stale commands, broken relative links, ambiguous implementation claims, and incorrect data-use
classification are documentation failures; formatting alone does not establish their correctness.
