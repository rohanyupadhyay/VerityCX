<!-- Defines the typed configuration, state, and report models for Feature 001. -->
# Data Model: Acquire τ³-Banking Data

Feature 001 persists only the reviewed TOML configuration and the external Git checkout. The Python models below are immutable in-memory boundary objects; they do not introduce an application database.

## Entity: `Tau3UpstreamConfig`

Represents the immutable external source pin.

| Field | Type | Validation |
|---|---|---|
| `repository_url` | `str` | Exactly `https://github.com/sierra-research/tau2-bench.git`; HTTPS; no credentials, query, or fragment. |
| `license_id` | `str` | Exactly `MIT` for this pin. |
| `tag` | `str` | Exactly `v1.0.1`. |
| `commit_sha` | `str` | Exactly 40 lowercase hexadecimal characters and, in production, `fc0055dc4e0a316c3f83133267fbd6faaa770992`. |

**Identity rule**: The full commit SHA is authoritative. Repository URL and tag binding are independent provenance constraints and must also match.

## Entity: `Tau3PathConfig`

Represents repository-root-relative locations declared in TOML.

| Field | Production value | Validation |
|---|---|---|
| `checkout` | `.cache/tau3-bench/` | Relative, no `..`, resolves beneath the VerityCX root. |
| `documents` | `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/` | Relative, beneath `checkout`, directory path. |
| `database` | `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json` | Relative, beneath `checkout`, file path. |
| `tasks` | `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/` | Relative, beneath `checkout`, directory path and evaluation-only. |

**Identity rule**: Config strings are the stable public values. Resolved absolute paths are derived for one explicit repository root and are never serialized back into the repository.

## Entity: `Tau3Config`

Aggregates configuration schema and immutable source/path values.

| Field | Type | Validation |
|---|---|---|
| `schema_version` | `int` | Exactly `1`; booleans are rejected even though they are integer subclasses in Python. |
| `upstream` | `Tau3UpstreamConfig` | Required and fully valid. |
| `paths` | `Tau3PathConfig` | Required and fully valid. |

**Boundary rule**: Missing tables/keys, unknown tables/keys, duplicate TOML definitions, and wrong value types fail configuration loading before any Git or filesystem mutation.

## Entity: `ResolvedTau3Paths`

Contains absolute paths computed from a caller-supplied VerityCX root.

| Field | Type | Relationship/invariant |
|---|---|---|
| `repository_root` | `Path` | Existing trusted root supplied by the script or test. |
| `cache_root` | `Path` | `repository_root / ".cache"`; must not be a link or junction. |
| `checkout` | `Path` | Resolved configured checkout beneath `cache_root`. |
| `documents` | `Path` | Resolved configured documents directory beneath `checkout`. |
| `database` | `Path` | Resolved configured database file beneath `checkout`. |
| `tasks` | `Path` | Resolved configured tasks directory beneath `checkout`. |

**Containment rule**: Lexical validation occurs before resolution; resolved containment and non-following link/junction checks occur before use.

## Entity: `GitCheckoutState`

Represents verified repository metadata without file content.

| Field | Type | Validation |
|---|---|---|
| `top_level` | `Path` | Same filesystem object as the checkout root. |
| `origin_url` | `str` | Sole local `remote.origin.url`, exact configured URL. |
| `head_sha` | `str` | Exact configured commit SHA. |
| `tag_sha` | `str` | Peeled configured tag commit, equal to `head_sha`. |
| `is_clean` | `bool` | True only when no-optional-locks porcelain output is empty. |

**Privacy rule**: Dirty-path entries are counted or categorized internally but never stored in public summaries or printed.

## Entity: `BankingDataState`

Represents successful structural validation of required banking paths.

| Field | Type | Validation |
|---|---|---|
| `document_count` | `int` | Positive recursive count of readable regular files; traversal follows no links/junctions. |
| `task_count` | `int` | Positive recursive count of readable regular files; task contents are not decoded. |
| `database_root` | internal typed JSON object | UTF-8, valid JSON, non-empty top-level object; retained only long enough to derive safe shapes. |

**Lifecycle rule**: Task file bytes may be minimally opened to prove readability but never decoded into task domain objects, returned, logged, indexed, or passed to prompts.

## Entity: `DatabaseCollectionShape`

Represents one safe top-level synthetic database entry.

| Field | Type | Validation |
|---|---|---|
| `name` | `str` | Top-level database key, sorted for deterministic output. |
| `json_kind` | enum-like `str` | One of `object`, `array`, `string`, `number`, `boolean`, or `null`. |
| `direct_count` | `int | None` | Number of direct entries/items for object/array only; `None` for scalar values. |

**Disclosure rule**: No nested key, record identifier, scalar value, sample, or source representation is retained.

## Entity: `InspectionSummary`

The complete public inspection result.

| Field | Type | Source |
|---|---|---|
| `tag` | `str` | Verified config/tag binding. |
| `commit_sha` | `str` | Verified `HEAD`. |
| `document_count` | `int` | `BankingDataState`. |
| `task_count` | `int` | `BankingDataState`; count only. |
| `database_collections` | `tuple[DatabaseCollectionShape, ...]` | Safe shapes derived from `db.json`. |

**Serialization rule**: `repr`, formatting, and any mapping conversion expose only these fields.

## Entity: `Tau3OperationError`

A typed expected failure suitable for CLI translation.

| Field | Type | Purpose |
|---|---|---|
| `category` | stable enum-like `str` | Machine-assertable class such as `origin-mismatch` or `malformed-database`. |
| `message` | `str` | Human action and expected/detected metadata, sanitized of source bodies and task/file listings. |
| `path` | `Path | None` | Only the relevant configured or current-run-owned path; never task filenames from recursive traversal. |

Expected failures produce exit code `1` without a traceback. Programming defects are not silently converted into successful results.

## Entity: `SetupExecution`

Transient ownership and lifecycle state for one default setup invocation.

| Field | Type | Invariant |
|---|---|---|
| `mode` | `existing`, `check`, or `install` | Chosen before mutation. |
| `owns_lock` | `bool` | True only after this process atomically creates the cooperative lock. |
| `staging_parent` | `Path | None` | Unique absolute directory created by this execution only. |
| `staging_checkout` | `Path | None` | Initially nonexistent child passed to Git clone. |
| `promoted` | `bool` | True only after complete staged validation and non-replacing same-filesystem rename. |

### State Transitions

```text
TARGET_UNKNOWN
├── target exists ──> VALIDATING_EXISTING
│   ├── valid ──────> READY_EXISTING
│   └── invalid ────> FAILED_PRESERVED
└── target missing
    ├── check mode ─> FAILED_NO_CHECKOUT
    └── install ────> LOCKED
        ├── clone fails ───────────────> FAILED_CLEAN_OWNED_STAGING
        └── STAGED
            ├── validation fails ──────> FAILED_CLEAN_OWNED_STAGING
            └── VALIDATED_STAGING
                ├── target appeared ──> FAILED_PRESERVE_TARGET
                └── PROMOTED ─────────> READY_INSTALLED
```

`FAILED_*` cleanup is limited to `staging_parent` and the lock whose ownership flags belong to this execution. Existing checkout, stale staging, stale locks, and unrelated cache content are never automatically removed.

## Relationships and Data-Use Boundary

```text
Tau3Config
├── Tau3UpstreamConfig ──validates──> GitCheckoutState
└── Tau3PathConfig ──────resolves───> ResolvedTau3Paths
                                      ├── documents ──application-safe
                                      ├── database ───application-safe
                                      └── tasks ──────evaluation-only

GitCheckoutState + BankingDataState ──produce──> InspectionSummary
```

Everything beneath the upstream checkout is denied to application consumers unless it is the configured documents subtree or exactly the configured database file. Inspection's task access is limited to non-semantic traversal, readability, and count metadata.
