<!-- Documents the repository quality workflow and required status contract. -->

# Quality Workflows

## Purpose and Responsibility

`quality.yml` is the Git-root continuous-integration boundary for the root-level VerityCX project.
It runs the complete network-independent Feature 001 quality suite on Python 3.12 for
`ubuntu-latest`, `windows-latest`, and `macos-latest`. The workflow does not acquire the official
upstream repository, use credentials, or modify production cache state.

The Markdown gate also covers the proposed platform roadmap, design, threat model and the complete
Feature 002 specification directory. These checks validate documentation formatting, not future
runtime behavior or Feature 002 acceptance.

## Public Contract and Structure

The required status is the `quality / verify (<runner>)` matrix. Each job checks out project code,
installs Python 3.12 and uv 0.12.5, requires Git 2.34 or newer, and records the matrix label, runner
name/OS/architecture, hosted `ImageOS`/`ImageVersion`, and tool versions. It uses locked
dependencies, records the monotonic local-fixture first-acquisition duration, fails at 600 seconds
or more, and runs Ruff, mdformat, yamlfix, strict mypy, and the full network-independent pytest
suite, including real repository-root CLI parser checks. Test-created clones configure their own
local commit identity instead of requiring developer-global Git settings. The timed test starts its clock after fixture construction and immediately before the setup
operation, then stops it only after validated promotion returns successfully; pytest startup,
collection, and fixture construction are outside the SC-001 interval.

All run steps use `defaults.run.working-directory: .`; Git-root workflow files are addressed
with `.github/workflows/`. The Git-root `.gitattributes` pins formatter-owned Python, Markdown, and YAML
to LF so Windows, Linux, and macOS check identical text. The directory contains only this
documentation and `quality.yml`.

## Dependencies and Configuration

The workflow depends on GitHub-hosted runner images, `actions/checkout`, `actions/setup-python`, and
`astral-sh/setup-uv`. Action majors and the exact uv tool version are explicit. Project dependency
versions remain governed by `pyproject.toml` and `uv.lock`; CI uses no unlocked install path.

## Usage, Tests, and Failure Modes

The workflow runs for every push and pull request, including changes to root-level tooling,
Spec Kit, and documentation. No nested-path filter can suppress the required root checks. Reproduce its
commands with `specs/001-acquire-tau3-banking/quickstart.md`. A failed platform job blocks the public
status contract; infrastructure retries must be recorded separately and cannot replace a product
failure. A missing/old Git, lock drift, formatting/lint/type/test error, disclosure regression, or
duration at or above ten minutes fails the corresponding job.

The only manual networked validation is the separately documented one-environment official smoke
test. It does not belong in this workflow.

## Feature 002 implementation

`quality.yml` runs database-free tests on Linux, Windows and macOS. `support-integration.yml` builds native PostgreSQL 18.6 on Ubuntu 24.04, creates separate admin/runtime roles, and runs the complete offline suite sequentially. No Docker or paid credentials are required. Workflow configuration is implemented; a hosted run has not been claimed.
