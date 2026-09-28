<!-- Records resolved technical decisions for repository dotenv support. -->

# Research: Repository Environment Configuration

## Decision 1: Use an explicit python-dotenv loader

**Decision**: Add `python-dotenv==1.2.3` as a direct locked dependency. A shared function calls
`load_dotenv(PROJECT_ROOT / ".env", override=False)` once at maintained process startup.

**Rationale**: The library is typed, platform-independent, supports Python 3.12, treats a missing
file as a nonfatal result, and makes process-precedence explicit. Supplying the absolute path avoids
its implicit `find_dotenv` traversal and satisfies the single-root constraint. Version 1.2.3 is the
current PyPI release and includes BOM handling useful for Windows-edited dotenv files.

**Alternatives considered**:

- A handwritten runtime parser was rejected because quoting, escaping, interpolation, encoding,
  and cross-platform behavior would become new security-sensitive application logic.
- `pydantic-settings` was rejected because the feature needs process-level acquisition shared by
  scripts and pytest, not a second settings model or changes to established validation behavior.
- Implicit `load_dotenv()` discovery was rejected because it can depend on stack/current-directory
  discovery and would weaken the repository-root invariant.

**Primary sources**: [python-dotenv reference](https://bbc2.github.io/python-dotenv/reference/) and
[PyPI release metadata](https://pypi.org/project/python-dotenv/).

## Decision 2: Keep acquisition at process entry points

**Decision**: `veritycx.environment.load_project_environment()` mutates only the process environment
and is called before argument/configuration handling by the API, worker, management, validation,
and pytest-session entry points. Existing functions that receive an explicit `Mapping[str, str]` or
`dict[str, str]` never call dotenv implicitly.

**Rationale**: One opt-in call per process makes precedence and side effects visible while allowing
all existing validation/default/failure behavior to remain unchanged. Explicit mappings used by
unit tests and child-process boundaries stay deterministic and do not inherit a developer file
unless their owning entry point deliberately loaded it.

**Alternatives considered**:

- Import-time loading was rejected because importing library code would mutate global state and
  contaminate isolated tests.
- Loading inside `load_configuration()` was rejected because callers deliberately pass a mapping;
  augmenting it would violate that interface and FR-013.
- Repeating dotenv parsing in each consumer was rejected because root and precedence behavior could
  drift.

## Decision 3: Derive the required inventory from AST reads and ownership rules

**Decision**: The contract checker parses maintained Python syntax with `ast`, collects literal
environment reads from `os.getenv`, `os.environ.get`, `os.environ[...]`, and recognized explicit
environment-mapping `.get(...)` calls, and classifies the results. `VERITYCX_` names are
project-owned by prefix; `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` are explicit
provider-owned exceptions adopted by VerityCX. Host/tool/CI names are external. Dynamic access that
could represent a project-owned name fails closed.

**Rationale**: Source reads remain the evidence, so `.env.example` cannot be made to pass merely by
editing a duplicate inventory. A small ownership policy is necessary to distinguish configuration
from ambient controls that maintained code forwards or inspects. Sorted paths/names and AST parsing
work identically on all supported hosts.

**Alternatives considered**:

- A standalone hard-coded list was rejected because it could drift in lockstep with the template
  while missing actual consumers.
- Grep/regular expressions were rejected because comments, strings, assignment targets, aliases,
  and formatting can produce unstable false positives.
- Scanning every environment key as project-owned was rejected because it would incorrectly expose
  `PATH`, GitHub Actions paths, build controls, and other externally managed settings.

## Decision 4: Use a strict example format and value-blind diagnostics

**Decision**: `.env.example` accepts comments and blank lines plus one assignment per project-owned
name. The checker validates lexical assignment form, normalized identifier spelling, duplicates,
and safe empty or unmistakable placeholder values. It reads only `.env.example`, never `.env`, and
diagnostics contain sorted names/categories but no values.

**Rationale**: A strict tracked contract is easier to audit than the full runtime grammar and can
distinguish duplicate/malformed/export-prefixed lines before semantic parsing would collapse them.
Runtime `.env` parsing remains python-dotenv's responsibility. Name-only output makes seeded secret
canaries safe in tests and CI logs.

**Alternatives considered**:

- Comparing `dotenv_values()` dictionaries alone was rejected because mappings erase duplicates
  and do not by themselves enforce the repository's placeholder policy.
- Reading the developer `.env` was rejected because values are neither needed for drift detection
  nor safe to expose to quality tooling.

## Decision 5: Enforce through the existing three-host quality path

**Decision**: Add `uv run python scripts/check_environment_contract.py` to the existing
Linux/Windows/macOS quality workflow and document the identical root command locally. Focused pytest
tests exercise failure classes; the live repository invocation proves the source/template pair.

**Rationale**: The current quality matrix already owns locked synchronization, formatting, lint,
typing, database-free tests, and documentation checks on all supported hosts. Extending that job
avoids a divergent gate while giving every pull request the requested drift enforcement.

**Alternatives considered**:

- A Linux-only job was rejected because FR-011 and SC-004 require every supported host.
- A pre-commit-only check was rejected because local hooks are optional and do not enforce merges.
