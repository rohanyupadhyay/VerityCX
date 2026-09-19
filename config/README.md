<!-- Documents the fixed tau3 configuration module and its safety boundary. -->

# τ³ Configuration

## Purpose and Responsibility

`config/` owns reviewed, production-readable configuration for external data dependencies. For
Feature 001, `tau3-bench.toml` is the sole production source of truth for the upstream identity and
project-relative paths.

## Public Contract

Schema version 1 contains exactly:

- `schema_version = 1`
- upstream URL `https://github.com/sierra-research/tau2-bench.git`
- MIT licence identifier
- tag `v1.0.1`
- commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`
- checkout, documents, database, and tasks paths beneath the project root

Unknown, missing, duplicate, wrongly typed, absolute, drive-qualified, UNC, parent-traversing, or
non-production values fail as `configuration-invalid` before Git or cache mutation.

## Boundaries

Production commands do not accept a config path, repository, tag, SHA, or destination override.
Tests may directly construct a typed `Tau3Config` for temporary local remotes; that injection is not
available from either public CLI.

## Dependencies and Usage

Python 3.12 `tomllib` parses the file. `veritycx.data_sources.tau3.load_tau3_config()` validates the
closed schema, and `resolve_tau3_paths()` resolves it from an explicit script-derived project root.

Run the focused tests with:

```text
uv run pytest tests/data_sources/test_tau3.py
```

Configuration changes require a reviewed specification and dependency-pin update. Never edit the
pin merely to repair an existing local checkout.

## Support Defaults

`support.toml` contains closed, nonsecret Feature 002 settings. Load it using
`veritycx.service.configuration.load_configuration` from root commands; unknown keys, public binds
and invalid limits fail safely. Supply runtime DSN/auth path via `VERITYCX_DATABASE_URL` and
`VERITYCX_AUTH_FILE`; credentials do not belong in TOML. Live provider/export settings require their
explicit environment credentials. Test with `uv run pytest tests/support/unit/test_configuration.py`.

## Feature 002 implementation

Tracing is disabled by default, including inherited graph auto-tracing. Enabling `traces_enabled` requires an explicit project and key and sends only allow-listed metadata through the fixed LangSmith endpoint. The service defaults to loopback, ten jobs, a twenty-connection pool, 8,000-character messages, 100 customer turns and thirty-day retention.
