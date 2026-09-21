<!-- Documents the root-level test suite and its network-independent contracts. -->

# Tests

Run all commands from the Git repository root, never from this directory.

## Responsibilities and Structure

- `test_repository_layout.py` resolves Git's top level and runs the real setup, check, and
  inspection argument parsers there. Moving the scripts below a nested project breaks these tests.
- `data_sources/test_tau3.py` exercises acquisition, preservation, Git/filesystem boundaries, and
  safe output using temporary local repositories and generated synthetic data.
- [Data-source test guidance](data_sources/README.md) describes the detailed safety coverage.

## Interfaces, Dependencies, and Configuration

These are pytest tests, not application APIs. They require Git and the Python 3.12 development
environment defined by root `pyproject.toml` and `uv.lock`. Root-command checks also require a Git
checkout, as in local development and CI. No test reads the production cache or contacts GitHub.
Synthetic repositories that create commits supply local author identity, not global user settings.

## Usage and Failure Modes

```text
uv sync --locked
uv run pytest tests -m "not support_db and not live"
uv run ruff check src scripts tests
uv run mypy --strict src scripts tests
```

Missing Git, missing root scripts, or a broken package installation fails the root checks.
Capability-only file-symlink cases may skip on Windows without link privileges; injected safety
checks and available junction cases remain required. Full three-OS hosted acceptance is separate
from a passing local suite.

## Durable Support Tests

`support/` contains synthetic unit/contract tests and marked native PostgreSQL integration tests.
Run database-free coverage with `uv run pytest tests -m "not support_db and not live"`.
Full offline coverage uses `uv run pytest tests -m "not live"` and requires explicit
`VERITYCX_TEST_DATABASE_URL` and `VERITYCX_TEST_MIGRATION_DATABASE_URL` for the dedicated test database.
Missing database configuration fails marked tests; it is not counted as a successful skip.
On Linux/WSL, create or reuse the guarded project-owned database and load its generated environment
before running full offline coverage:

```text
uv run python scripts/setup_support_local.py
source .cache/support/local/test.env
output=$(uv run python scripts/manage_support.py corpus prepare --mode synthetic)
hash=${output##*hash=}
uv run python scripts/manage_support.py corpus approve --hash "$hash"
uv run pytest tests -m "not live"
```

See `support/README.md` for ownership and fixture boundaries. Package markers support typed imports
of the shared test harness; tests are not runtime application interfaces.
