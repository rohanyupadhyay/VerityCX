<!-- Defines the configuration-contract entities and validation transitions for dotenv support. -->

# Data Model: Repository Environment Configuration

This feature adds no database entities. Its data is a small repository configuration contract.

## Local Environment File

| Field | Type | Rules |
| --- | --- | --- |
| Path | absolute `Path` | Exactly `<git-root>/.env`; no current-directory or parent discovery. |
| Presence | boolean | Optional; absence is a successful no-op. |
| Assignments | name/value mapping | Parsed by python-dotenv; empty values stay empty. |
| Version-control state | local file | `.env` and local variants are ignored and never inspected by the contract checker. |

Transition: `absent -> present` when a developer copies `.env.example`; loading does not modify the
file. Process values merge over file values because `override=False`.

## Example Environment Contract

| Field | Type | Rules |
| --- | --- | --- |
| Path | absolute `Path` | Exactly `<git-root>/.env.example`; tracked. |
| Name | uppercase identifier | One assignment per name; exact case; no `export` prefix. |
| Value | empty or safe placeholder | No usable token, password, private path, or connection string. |
| Comments/blanks | non-entry line | Ignored for name comparison. |

The initial normalized name set is:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `OPENAI_API_KEY`
- `VERITYCX_AUTH_FILE`
- `VERITYCX_DATABASE_URL`
- `VERITYCX_MIGRATION_DATABASE_URL`
- `VERITYCX_TEST_DATABASE_URL`
- `VERITYCX_TEST_MIGRATION_DATABASE_URL`
- `VERITYCX_VALIDATION_CORPUS`
- `VERITYCX_VALIDATION_PROVIDER`

## Environment Read Evidence

| Field | Type | Rules |
| --- | --- | --- |
| Name | string literal | Derived from a maintained AST read, never from a value or comment. |
| Source | root-relative path and line | Used for deterministic diagnostics and review. |
| Access kind | enum | `getenv`, `mapping-get`, or `mapping-subscript`. |
| Ownership | enum | `project`, `external`, or `invalid-dynamic`. |

Project ownership is assigned to `VERITYCX_*` reads and the three adopted provider settings.
Operating-system, shell, Git, package/build, PostgreSQL bootstrap, and GitHub Actions names remain
external. An unclassifiable dynamic project access is invalid rather than silently omitted.

## Contract Check Result

| Field | Type | Rules |
| --- | --- | --- |
| Required names | `frozenset[str]` | Project-owned names derived from source evidence. |
| Example names | ordered tuple | Parsed names retain duplicates until validation completes. |
| Findings | sorted tuple | Categories: missing, extra, duplicate, malformed, wrong-case, unsafe-placeholder, dynamic. |
| Exit status | integer | `0` only for an exact safe contract; `1` for contract findings; usage failures follow argparse. |

Diagnostics disclose finding categories, names, and safe source locations only. They never include
example values, local dotenv values, or inherited process values.

## Validation Flow

1. Resolve the one project root from the checker module location.
1. Parse configured maintained Python scopes and collect environment-read evidence.
1. Apply ownership rules and reject unsupported dynamic project reads.
1. Parse `.env.example` lexically without opening `.env`.
1. Validate identifiers, duplicates, placeholder safety, and exact set equality.
1. Return stable sorted diagnostics or `environment_contract_ok`.
