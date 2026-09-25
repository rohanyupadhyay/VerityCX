<!-- Defines the public dotenv and environment-contract checker behavior. -->

# Environment Configuration Contract

## Root dotenv loading

`veritycx.environment.load_project_environment()` loads only `<git-root>/.env` into the current
process. It accepts no discovery root from the caller and never searches a parent, child, or current
working directory.

- Existing process names win over file assignments.
- A missing `.env` succeeds without output or invented defaults.
- Parse/load failures are surfaced without printing values.
- Library functions receiving explicit environment mappings do not invoke the loader.
- Maintained API, worker, management, validation, and pytest startup paths invoke it before their
  first project-owned environment read.

The acquisition boundary does not change which values are required or optional. Existing consumer
validation remains authoritative.

## `.env.example`

The tracked root template contains every and only the ten project-owned names defined in
[data-model.md](../data-model.md). Each name occurs once using exact uppercase spelling. Values are
empty or unmistakable nonsecret placeholders; no real database string, token, password, private
path, or credential is permitted.

Comments and blank lines do not create entries. Malformed assignments, `export` prefixes,
duplicates, case variants, missing names, and extra names invalidate the contract. The real `.env`
and all local variants remain ignored.

## Contract checker CLI

Run from any current directory while selecting the root project in the usual uv manner:

```text
uv run python scripts/check_environment_contract.py
```

The no-argument command resolves its source scope and `.env.example` from the script's Git root.
Success prints exactly one stable status line and exits `0`. Contract drift prints sorted,
category-prefixed name-only diagnostics and exits `1`. Invalid command usage follows argparse and
exits `2`.

The command:

1. derives literal environment reads from maintained Python ASTs;
1. applies the documented project/external ownership policy;
1. parses the example without opening `.env`;
1. compares exact normalized name sets and validates duplicate/format/placeholder rules.

Diagnostics may include a root-relative source location for a read. They must never contain a
dotenv, example, or process value. Host/tool/CI controls are excluded unless the source and policy
deliberately reclassify them as project-owned.
