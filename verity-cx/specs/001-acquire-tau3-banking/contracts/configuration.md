<!-- Defines the reviewed TOML configuration contract for Feature 001. -->

# Contract: τ³-Banking Configuration

## Location and Authority

Production setup and inspection MUST load exactly `config/tau3-bench.toml` beneath the VerityCX repository root. This file is the only production source of truth for the external dependency pin and paths. Environment variables and command-line options MUST NOT override it.

## Schema Version 1

```toml
# Pins the external tau3-Banking repository and required data paths.
schema_version = 1

[upstream]
repository_url = "https://github.com/sierra-research/tau2-bench.git"
license = "MIT"
tag = "v1.0.1"
commit_sha = "fc0055dc4e0a316c3f83133267fbd6faaa770992"

[paths]
checkout = ".cache/tau3-bench/"
documents = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/"
database = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json"
tasks = ".cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/"
```

## Validation Contract

- The top-level key set MUST be exactly `schema_version`, `upstream`, and `paths`.
- The `upstream` key set MUST be exactly `repository_url`, `license`, `tag`, and `commit_sha`.
- The `paths` key set MUST be exactly `checkout`, `documents`, `database`, and `tasks`.
- Missing keys, unknown keys, duplicate TOML declarations, incorrect types, or unsupported schema versions MUST fail before Git or cache mutation.
- `schema_version` MUST be integer `1`, not boolean `true`.
- Production upstream values MUST exactly match the literals shown above.
- The SHA MUST also pass a general 40-character lowercase hexadecimal validation before exact comparison.
- Every configured path MUST be a non-empty relative path using repository-root-relative semantics. Absolute paths, drive-qualified paths, UNC paths, parent traversal, or resolved escape from the explicit repository root MUST fail.
- `documents`, `database`, and `tasks` MUST resolve beneath `checkout` at their exact declared locations.
- Path resolution MUST use the explicit VerityCX root passed by the script/test, never the current working directory.

## Test Injection

Tests MAY construct `Tau3Config` objects directly with temporary repository URLs, tags, SHAs, and roots. This typed injection is internal to the test/library boundary and MUST NOT create a production CLI override.
