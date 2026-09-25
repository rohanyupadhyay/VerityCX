<!-- Defines the implementation approach and verification gates for repository dotenv support. -->

# Implementation Plan: Repository Environment Configuration

**Branch**: `symphony/gh-5-env-support` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/gh-5-env-support/spec.md`

**Status**: Phase 0 research and Phase 1 design complete; implementation not started.

## Summary

Add one typed, root-anchored environment-loading boundary backed by `python-dotenv` 1.2.3 and call
it only from maintained runtime, management, validation, and pytest startup entry points. Explicit
process values remain authoritative because loading uses an absolute root `.env` path with
`override=False`; library code that accepts an explicit environment mapping remains free of ambient
loading.

Track a root `.env.example` containing the ten project-owned names in the specification. Add a
value-blind contract command that statically derives literal environment reads from maintained
Python consumers, applies a documented ownership rule, strictly parses the template, and reports
name-only missing, extra, duplicate, malformed, and unsafe-placeholder categories. Unit and contract
tests cover loading and drift cases; the command joins the three-host quality workflow and the
documented local gate.

## Technical Context

**Language/Version**: Python 3.12; uv 0.12.5; strict mypy and Ruff conventions.

**Primary Dependencies**: Existing project dependencies plus `python-dotenv==1.2.3`. Its public
`load_dotenv(dotenv_path=..., override=False)` interface supplies explicit-path, non-overwriting
loading; implementation code does not use implicit `find_dotenv` discovery. The checker uses the
Python standard-library AST and a strict project-authored template parser rather than a second
dependency.

**Storage**: Root `.env` for ignored developer-local values and tracked root `.env.example` for the
name-only configuration contract. No database, schema, or persistent application-data change.

**Testing**: Existing pytest, Ruff, strict mypy, mdformat, yamlfix, and Git diff/secret review.
Focused unit tests use temporary dotenv/template/source files and explicit environment mappings;
contract tests run the real repository checker.

**Target Platform**: Repository-root commands on supported Linux, Windows, and macOS GitHub-hosted
runners. Paths use `pathlib.Path`; no shell-specific sourcing is required.

**Project Type**: Python package with local API/worker entry points, root developer scripts, and a
pytest suite.

**Performance Goals**: Root loading and the contract check remain startup/build-time work only. The
checker completes within the ordinary three-host quality job and scans only maintained Python
files in the repository.

**Constraints**: Never overwrite an existing process value; missing `.env` is a no-op; never print
or validate a real `.env` value; never discover a dotenv file outside the Git root; preserve
explicit environment-mapping isolation; report only deterministic names and categories.

**Scale/Scope**: Ten initial project-owned names across `src/veritycx/`, `scripts/`, and the support
test configuration boundary. Host, shell, Git, uv, PostgreSQL-build, and GitHub Actions controls are
classified as external and omitted from `.env.example`.

## Constitution Check

Pre-research and post-design reviews pass all six principles without exception.

| Principle | Design response | Implementation gate |
| --- | --- | --- |
| I. Module documentation | Update root, package, scripts, tests, service, and workflow READMEs for changed responsibilities. | README review covers purpose, configuration, commands, precedence, ownership, and failures. |
| II. File-level documentation | New Python files begin with module docstrings; Markdown/YAML retain conventional leading comments. `.env.example` is documented by the nearest root README because dotenv comments are data-bearing and no synthetic header is required. | Ruff documentation lint plus file inventory review. |
| III. Interface documentation | Loader and checker functions/classes receive typed docstrings; ownership and value-blind diagnostics are explained at the decision point. | Ruff, strict mypy, and reviewer inspection. |
| IV. Strict typing | Public loader/checker contracts use explicit paths, mappings, immutable result models, and validated AST/parser boundaries; no `Any`, unchecked cast, or ignored diagnostic is planned. | `uv run mypy --strict src scripts tests`. |
| V. Automated gates | Add focused pytest coverage and invoke the real contract checker in the existing Linux/Windows/macOS quality job; retain formatter, lint, type, docs, and test gates. | Locked install and all current quality commands pass without rewrite. |
| VI. Single project root | `.env`, `.env.example`, loader root, checker scope, docs, tests, and CI all resolve from the one Git root; no current-working-directory discovery or wrapper root. | Existing layout tests plus non-root-cwd loader/checker tests. |

No constitution amendment, complexity exception, nested project, or undocumented quality bypass is
required.

## Project Structure

### Documentation (this feature)

```text
specs/gh-5-env-support/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── contracts/
    ├── README.md
    └── environment.md
```

`tasks.md` is produced only after plan approval by `$speckit-tasks`.

### Source Code (repository root; planned changes)

```text
.env.example                         # Exact, safe project-owned name contract
.gitignore                           # Ignore .env variants while allowing .env.example
pyproject.toml                       # Direct python-dotenv pin
uv.lock                              # Reproducible dependency resolution
README.md                            # Root setup and quality command
src/veritycx/
├── README.md                        # Package configuration boundary
├── environment.py                   # Root path and non-overwriting dotenv loader
├── service/
│   ├── README.md
│   └── main.py                      # API startup loading call
└── orchestration/
    └── worker.py                    # Worker startup loading call
scripts/
├── README.md
├── manage_support.py                # Management startup loading call
├── validate_support.py              # Validation startup loading call
└── check_environment_contract.py    # AST/template drift checker CLI
tests/
├── README.md
├── conftest.py                      # Intentional pytest-session dotenv opt-in
├── unit/
│   └── test_environment.py          # Loader precedence/root/missing-file tests
└── contract/
    └── test_environment_contract.py # Parser, ownership, drift, secrecy tests
.github/workflows/
├── README.md
└── quality.yml                      # Three-host contract gate
```

**Structure Decision**: Extend the existing single root Python package and its root scripts. The
loader belongs in `veritycx.environment` because runtime, management, validation, and tests share
the root/path/precedence policy. The checker remains a developer script because it validates source
and repository artifacts rather than serving runtime requests. No existing application data model
or API surface changes.

## Implementation Sequence

1. Pin and lock `python-dotenv`, add the tracked safe template, and correct ignore negation so the
   example remains tracked while all real/local dotenv variants stay ignored.
1. Implement and unit-test the absolute-root, `override=False` loader. Invoke it once at each
   process entry point before any environment read; do not call it from configuration functions
   that accept explicit mappings.
1. Implement the typed static inventory and strict template comparison command. Scan literal reads,
   distinguish project-owned names by documented rules, fail closed on dynamic project-owned
   access, and emit sorted name-only diagnostics.
1. Add contract fixtures for complete, missing, extra, duplicate, malformed, wrong-case,
   export-prefixed, unsafe-value, missing-file, precedence, non-root-cwd, and secret-canary cases.
1. Update configuration and quality documentation, add the checker to the existing three-host
   quality workflow, and run every repository gate from the Git root.

## Requirements and Evidence Ownership

| Requirements | Design owner | Evidence |
| --- | --- | --- |
| FR-001, FR-005–FR-008 | Root `.env.example`, `.gitignore`; [environment contract](contracts/environment.md) | Tracked/ignored assertions, exact-name fixtures, placeholder and secret-canary tests. |
| FR-002–FR-004, FR-012–FR-013 | `veritycx.environment` plus explicit entry-point calls | Precedence, absent-file, non-root-cwd, entry-point, and explicit-mapping isolation tests. |
| FR-009–FR-010 | `scripts/check_environment_contract.py` | Seeded drift/parser/AST cases and real-repository contract test with value-blind output assertions. |
| FR-011 | `.github/workflows/quality.yml`, root and workflow READMEs | Three-host job executes the documented checker after locked synchronization. |
| FR-014; SC-001–SC-006 | Affected module READMEs and [quickstart](quickstart.md) | Documentation formatting, full quality gates, diff/secret review, and runnable scenarios. |

## Phase Outputs and Verification

Phase 0 decisions are recorded in [research.md](research.md). Phase 1 defines the configuration
entities in [data-model.md](data-model.md), the public developer contract in
[contracts/environment.md](contracts/environment.md), and runnable acceptance evidence in
[quickstart.md](quickstart.md). No unresolved planning questions or constitution violations remain.
