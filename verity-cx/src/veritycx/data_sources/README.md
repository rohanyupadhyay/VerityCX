<!-- Documents the typed external-data adapter and its security invariants. -->

# External Data Sources

## Purpose and Responsibilities

`data_sources/` owns typed configuration, path containment, Git execution, required-data validation,
transactional setup, and safe inspection for external dependencies. `tau3.py` is the sole Feature
001 adapter; `__init__.py` declares its public imports.

Public interfaces are the immutable `Tau3Config` family, `ResolvedTau3Paths`, `GitCheckoutState`,
`BankingDataState`, `DatabaseCollectionShape`, `SetupResult`, `InspectionSummary`,
`Tau3OperationError`, `load_tau3_config()`, `resolve_tau3_paths()`, `setup_tau3_data()`, and
`inspect_tau3_data()`.

## Layers and Dependencies

1. The configuration layer accepts only the closed production schema or an explicitly constructed
   test configuration.
1. The filesystem layer rejects absolute, escaping, linked, junction, special, and unreadable
   objects without following or replacing them.
1. The Git layer uses a resolved executable, argument sequences, `shell=False`, disabled prompts and
   optional locks, exact provenance checks, and sanitized failures.
1. The banking layer counts readable regular files and retains only safe top-level JSON shapes.

Runtime dependencies are Python 3.12's standard library and Git 2.34 or newer. No API key, network
SDK, alternate source, or application data loader is supported.

## Setup Transaction

`setup_tau3_data()` classifies the destination before creating cache state. Valid existing and check
modes are offline and non-mutating. First installation claims `tau3-bench.setup.lock`, creates one
unique `tau3-bench-staging-*` directory on the cache filesystem, clones the exact tag, validates the
staged checkout, rechecks the destination, performs a non-replacing rename, and validates again.
Cleanup targets only the invocation-owned lock and staging parent; promoted or unowned state is
never rolled back, reset, repaired, or deleted.

## Inspection and Default-Deny Policy

`inspect_tau3_data()` performs two complete observations and returns an immutable summary only when
they match. The summary permits tag, SHA, aggregate counts, and top-level collection name, JSON kind,
and direct object/array count. Its representation and normal dataclass serialization retain no
filenames, nested keys, values, bodies, prompts, answers, reference actions, or grading data.

Only configured banking documents and exactly `db.json` are eligible for later application use.
Tasks and all other upstream paths are evaluation-only or unclassified and remain default-denied.
This module intentionally exposes no generic upstream reader.

## Failures and Verification

Expected boundary failures use stable `Tau3OperationError` categories. A concurrent inspection
difference is `checkout-changed`; ownership conflicts and cleanup failures preserve state and direct
manual recovery. Programming errors remain visible rather than being mislabeled as expected success.

```text
uv run ruff check src/veritycx/data_sources/tau3.py
uv run mypy --strict src
uv run pytest tests/data_sources/test_tau3.py
```
