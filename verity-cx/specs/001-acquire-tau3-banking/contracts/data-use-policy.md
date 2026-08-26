<!-- Defines the default-deny application and evaluation data boundary for Feature 001. -->

# Contract: τ³-Banking Data-Use Policy

## Governing Rule

All content acquired beneath `.cache/tau3-bench/` is denied to VerityCX application consumers by default. Only the two explicit application-safe entries below are exceptions.

## Classification Matrix

| Classification | Exact scope | Permitted Feature 001 access | Later application use |
|---|---|---|---|
| Application-safe knowledge | `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/` and descendants | Validate path, containment, file kind/readability, and count; never print bodies or names | Later retrieval/indexing/prompt use is permitted, subject to that feature's own safety controls. |
| Application-safe synthetic state | Exactly `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json` | Validate UTF-8 JSON and top-level object; derive only safe collection shapes | Later isolated synthetic banking state is permitted; raw records are not inspection output. |
| Evaluation-only tasks | `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/` and all descendants | Non-semantic traversal, regular-file/readability validation, and aggregate count only | Forbidden from prompts, indexes, runtime agents, application loaders, and APIs. |
| Evaluation-only aggregates | `tasks.json`, `tasks_voice.json`, and equivalent task collections | No Feature 001 application/inspection access | Forbidden from prompts, indexes, runtime agents, application loaders, and APIs. |
| Evaluation semantics | Task instructions, prompts, reference/golden actions, grading criteria, expected answers, reward data, and equivalents wherever stored | No semantic decoding, logging, reporting, or return | Evaluation tooling only; no runtime exposure. |
| External-only/default denied | Upstream source, `prompts/`, examples, simulations, and every other non-allow-listed path | Git-level acquisition/provenance only | Not VerityCX application data. |

## Enforcement Invariants

1. No generic function may expose an arbitrary path beneath the upstream checkout to application code.
1. Application-safe checks require both lexical containment and resolved containment, with symbolic links, junctions, and special files rejected.
1. Setup may prove task-file readability but MUST NOT JSON-decode task files or include filenames/status entries in public errors.
1. Inspection may emit only the total task-file count. It MUST NOT emit task filenames, sizes, fields, values, samples, or parse errors derived from task bodies.
1. Inspection may emit top-level database collection names, JSON kinds, and direct array/object counts. It MUST NOT emit nested keys, record identifiers, scalar values, samples, or raw JSON errors containing source text.
1. Success objects, exception messages, logs, stdout, stderr, `repr`, and any supported serialization MUST follow the same non-disclosure boundary.
1. Future features that consume application-safe data MUST re-enforce this allow-list; they may not infer safety from mere membership in the checkout.

## Test Contract

Automated tests generate unique canaries for document bodies, nested database values, task prompts, expected answers, reference actions, and grading criteria. Every success and expected-error output channel plus inspection report representations MUST be asserted free of all canaries. Tests MUST generate this synthetic material at runtime and MUST NOT commit upstream task content.
