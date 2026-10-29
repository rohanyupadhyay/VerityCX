<!-- Records the implementation and verification plan for scripted local app setup. -->

# Local App Setup Implementation Plan

**Goal:** Extend the existing PostgreSQL bootstrap with `--app` so local users need no
manual SQL or password copying to configure the application.

**Architecture:** Preserve the default dedicated-test setup. App mode reuses that owned
cluster, provisions a separate `veritycx_support` database and limited runtime role,
reuses the migration and demo-authentication helpers, and fills only missing or empty
settings in the root `.env`. Existing nonempty settings must match the generated app
configuration or setup fails without replacing them. Synthetic corpus approval remains
an explicit operation; setup reports whether it is available.

**Tech stack:** Existing Python 3.12, Psycopg, python-dotenv, pytest, and native PostgreSQL.

## Constraints and Review Focus

- Preserve default CLI output, test credentials, test database, and ownership checks.
- Keep generated credentials stable on rerun and private; never print secret values.
- Refuse adoption of an existing app database/role without saved setup credentials.
- Preserve existing dotenv content and refuse malformed or conflicting configuration.
- App mode must reuse valid authentication and reject partial credential sets.
- Read-only `--app --check` must never provision resources or write configuration.
- Never silently approve a document collection or enable a paid provider.

## Task 1: Bootstrap and configuration

- [x] Add failing contract tests for app-mode CLI checks, dotenv preservation/conflicts,
  private credentials, and safe authentication reuse.
- [x] Extend `scripts/setup_support_local.py` with `--app`, stable app credentials,
  separate app database provisioning, dotenv generation, and read-only app checks.
- [x] Run contract tests and lint/type checks; verify default setup compatibility.

## Task 2: Documentation and full validation

- [x] Update the root README, scripts README, support contract README, and quickstart
  with the one-command app setup and explicit corpus approval commands.
- [x] Exercise real app bootstrap and rerun against the existing owned local cluster.
- [x] Verify API readiness, a deterministic cited answer, and database isolation.
- [x] Run the full offline test suite sequentially plus formatting, type checks, and
  environment-contract validation. Review the final diff and leave changes uncommitted.

## Validation Record

The final full offline suite passed 349 tests against the dedicated native PostgreSQL
test database. Formatting, Ruff, strict mypy, Markdown formatting, environment-contract,
lockfile, and whitespace checks passed. Real application smoke checks verified HTTP
readiness, a cited synthetic answer, app-role denial of test-database access, and stable
credentials/configuration across reruns. Review identified dotenv interpolation and
uncaught migration errors; both received failing regression tests and fixes. No paid
provider calls or hosted acceptance runs were performed.
