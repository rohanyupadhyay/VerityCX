<!-- Provides runnable validation scenarios for repository dotenv support. -->

# Quickstart: Validate Repository Environment Configuration

These scenarios are the planned end-to-end evidence for Feature GH-5. Run commands from the Git
root with Python 3.12 and uv 0.12.5 after implementation.

## 1. Synchronize the locked project

```text
uv lock --check
uv sync --locked
```

Expected: the lock is current and the environment includes the pinned python-dotenv dependency.

## 2. Validate the tracked contract

```text
uv run python scripts/check_environment_contract.py
```

Expected: exit `0` and `environment_contract_ok`. The command must not require or inspect `.env`.

## 3. Exercise focused behavior

```text
uv run pytest tests/unit/test_environment.py tests/contract/test_environment_contract.py
```

Expected: precedence, missing-file, root resolution, explicit-mapping isolation, exact inventory,
and all seeded drift/parser/secret-canary cases pass without a canary value in captured output.

## 4. Exercise dotenv-only runtime acquisition

Copy `.env.example` to `.env`, populate only synthetic/dedicated local values needed for the chosen
command, and start a representative command without exporting those names manually:

```text
uv run python -m veritycx.service.main
```

Expected: the command passes environment acquisition and reaches its existing configuration/runtime
outcome. Re-run with one name explicitly set in the invoking process; the explicit value wins. Move
or remove `.env`; the command returns its established missing-configuration category rather than a
dotenv-specific crash. Never commit the local file.

## 5. Run repository quality gates

```text
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy --strict src scripts tests
uv run pytest tests -m "not support_db and not live"
uv run mdformat --check README.md .github/workflows/README.md src scripts tests specs/gh-5-env-support
uv run yamlfix --check .github/workflows/quality.yml .github/workflows/support-integration.yml
git diff --check
```

Expected: all commands pass from the one Git root. The GitHub quality matrix additionally invokes
the contract checker on Linux, Windows, and macOS.

## 6. Review tracked content for secrets and scope

```text
git ls-files '.env*'
git diff --cached --check
```

Expected after implementation: `.env.example` is the only tracked dotenv file; its values are empty
or obvious placeholders. Review the full diff to confirm no credential, local path, generated file,
or unrelated change is present.
