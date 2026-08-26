<!-- Documents the repository quality workflow and required status contract. -->

# Quality Workflows

## Purpose and Responsibility

`quality.yml` is the Git-root continuous-integration boundary for the nested `verity-cx/` project.
It runs the complete network-independent Feature 001 quality suite on Python 3.12 for
`ubuntu-latest`, `windows-latest`, and `macos-latest`. The workflow does not acquire the official
upstream repository, use credentials, or modify production cache state.

## Public Contract and Structure

The required status is the `quality / verify (<runner>)` matrix. Each job checks out project code,
installs Python 3.12 and uv 0.12.5, requires Git 2.34 or newer, records runner image and tool versions,
uses locked dependencies, records the local-fixture first-acquisition duration, and runs Ruff,
mdformat, yamlfix, strict mypy, and the full network-independent pytest suite.

All run steps use `defaults.run.working-directory: verity-cx`; Git-root workflow files are addressed
with `../.github/workflows/`. The directory contains only this documentation and `quality.yml`.

## Dependencies and Configuration

The workflow depends on GitHub-hosted runner images, `actions/checkout`, `actions/setup-python`, and
`astral-sh/setup-uv`. Action majors and the exact uv tool version are explicit. Project dependency
versions remain governed by `pyproject.toml` and `uv.lock`; CI uses no unlocked install path.

## Usage, Tests, and Failure Modes

The workflow runs for pushes and pull requests that affect the project or workflow. Reproduce its
commands with `specs/001-acquire-tau3-banking/quickstart.md`. A failed platform job blocks the public
status contract; infrastructure retries must be recorded separately and cannot replace a product
failure. A missing/old Git, lock drift, formatting/lint/type/test error, disclosure regression, or
duration at or above ten minutes fails the corresponding job.

The only manual networked validation is the separately documented one-environment official smoke
test. It does not belong in this workflow.
