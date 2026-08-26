<!-- Defines the safe human-readable inspection output for Feature 001. -->

# Contract: τ³-Banking Inspection CLI

## Command

```text
uv run python scripts/inspect_tau3_banking_data.py
```

The command has no production source/path override and performs no clone, fetch, repair, lock creation, staging creation, or cache mutation.

When the caller is outside the project root, the equivalent absolute-path form is `uv run --project <absolute-project-root> --locked python <absolute-project-root>/scripts/inspect_tau3_banking_data.py`. The explicit uv project selection supplies the same locked package environment without changing the caller's working directory or modifying `PYTHONPATH`/`sys.path`.

## Preconditions

Inspection loads the reviewed config and invokes the same non-mutating validator used by setup `--check`. The checkout must have the exact origin, `HEAD`, tag binding, clean status, and valid banking paths. Inspection derives a buffered summary, repeats identity, cleanliness, required-path, count, and database-shape validation, and emits the summary only when both observations agree. A missing, invalid, dirty, unreadable, or detectably changing checkout fails with no partial stdout and no mutation.

## Exit Codes and Streams

| Code | Meaning |
|---|---|
| `0` | Validation and inspection succeeded. |
| `1` | Expected configuration, checkout, Git, filesystem, or database failure. |
| `2` | Command-line usage error. |

Success is written to stdout. Categorized diagnostics are written to stderr. Expected failures do not print tracebacks or partial summaries.

Expected diagnostics use the shared setup shape, `error[category]: reason=...; path="..."; recovery=...`. The JSON-escaped `path` field is omitted only when no configured or current-run-owned path applies.

A detected difference between initial and final validation is `checkout-changed` with exit code `1`. Final validation does not claim to detect an actor that changes state and restores the identical validated state entirely between observations.

## Output Shape

Output is deterministic, line-oriented text:

```text
tag: v1.0.1
commit: fc0055dc4e0a316c3f83133267fbd6faaa770992
documents: <positive integer>
tasks: <positive integer>
database:
  <collection-name>: kind=<json-kind>, count=<integer>
  <collection-name>: kind=<json-kind>
```

Top-level database entries are sorted by collection name. `count` appears only for JSON arrays and objects and means direct items/entries, not a recursive count. JSON kinds are `object`, `array`, `string`, `number`, `boolean`, or `null`.

## Counting Contract

- Document and task counts are recursive counts of readable regular files beneath their configured directories.
- Traversal does not follow symbolic links or junctions and rejects special files or resolved path escape.
- Counts reveal no filenames, relative paths, sizes, timestamps, or contents.
- Task files are opened minimally for readability but are not decoded as JSON or mapped into task objects.

## Prohibited Output

Inspection results, stdout, stderr, expected-error messages, object representations, and any supported serialization MUST NOT contain:

- document filenames or bodies;
- nested database keys, record identifiers, customer values, scalar values, or samples;
- task filenames, instructions, prompts, user scenarios, reference/golden actions, grading criteria, reward data, or expected answers;
- raw JSON decode source text;
- raw Git porcelain entries or subprocess command lines.

The database collection name is the only allowed source-data key because high-level collection structure is an explicit feature requirement. Task count is the only allowed evaluation-directory observation.
