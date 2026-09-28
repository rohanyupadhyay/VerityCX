<!-- Documents focused unit tests for shared environment loading. -->

# Environment unit tests

`test_environment.py` validates the root-anchored dotenv loader, including process precedence,
missing files, empty values, repeat calls, parse failures, and secret-safe errors. Run it from the
Git root with `uv run pytest tests/unit/test_environment.py`.

Tests replace the loader's project root with a temporary directory and never read a developer's
real `.env`. A malformed file must fail with the fixed `invalid_environment_file` category without
including file values.
