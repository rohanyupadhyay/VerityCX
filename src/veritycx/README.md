<!-- Documents the importable VerityCX package and its public boundaries. -->

# `veritycx` Package

## Purpose and Responsibilities

`veritycx` contains reusable, strictly typed project behavior. The package currently exposes the
`data_sources` module, which owns external dependency configuration, validation, setup, and safe
structural reporting.

## Structure and Interfaces

```text
src/veritycx/
├── __init__.py
└── data_sources/
    ├── __init__.py
    └── tau3.py
```

Public exports are explicit in package `__init__.py` files. Project-root scripts import the package
under uv's editable `src`-layout installation; they never modify `PYTHONPATH` or `sys.path`.

## Dependencies and Configuration

Runtime code uses only the Python 3.12 standard library and the Git 2.34-or-newer executable. The
fixed τ³ pin and paths come from `config/tau3-bench.toml`; external TOML, JSON, subprocess, and
filesystem values are validated before entering typed application state.

## Usage and Tests

Developer-facing usage belongs to project-root scripts. Validate the package with:

```text
uv run ruff check src/veritycx
uv run mypy --strict src
uv run pytest tests/data_sources/test_tau3.py
```

## Constraints and Failure Modes

The package must not expose a generic upstream file reader, execute shell command strings, resolve
production paths from the current working directory, or return document, customer-record, or
evaluation semantics. Expected failures use `Tau3OperationError` with a stable category and
sanitized context; programming errors are not converted into successful results.
