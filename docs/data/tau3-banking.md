<!-- Defines provenance, use policy, commands, and scope for tau3-Banking data. -->

# τ³-Banking Data

## Provenance and Pin

- Producer: Sierra Research
- Official repository: `https://github.com/sierra-research/tau2-bench.git`
- Licence: MIT
- Release: `v1.0.1`
- Commit: `fc0055dc4e0a316c3f83133267fbd6faaa770992`

Setup downloads the dependency locally to `.cache/tau3-bench/`. The acquired checkout remains
external, ignored, and untracked; no upstream source or data is copied into maintained project files.

## Complete Paths

- Checkout: `.cache/tau3-bench/`
- Runtime-eligible documents:
  `.cache/tau3-bench/data/tau2/domains/banking_knowledge/documents/`
- Runtime-eligible synthetic state:
  `.cache/tau3-bench/data/tau2/domains/banking_knowledge/db.json`
- Evaluation-only tasks:
  `.cache/tau3-bench/data/tau2/domains/banking_knowledge/tasks/`

## Commands

```text
uv run python scripts/setup_tau3_data.py
uv run python scripts/setup_tau3_data.py --check
uv run python scripts/inspect_tau3_banking_data.py
```

Setup acquires once and validates thereafter; `--check` is explicitly read-only. Inspection reports
only the verified tag and SHA, recursive document/task file counts, and sorted top-level database
collection names, JSON kinds, and direct object/array counts. It never reports filenames, bodies,
nested keys, record values, task content, prompts, answers, reference actions, or grading data.

## Application Allow-List

Later features may index, retrieve, or place in runtime prompts only files beneath the configured
`documents/` directory. They may use only the configured `db.json` as synthetic banking state. A
future consumer must trace every input to this allow-list and reject everything else before loading,
indexing, prompting, API exposure, or agent use.

## Evaluation-Only and Default-Deny Inputs

The complete `tasks/` subtree, `tasks.json`, `tasks_voice.json`, instructions, evaluation prompts and
criteria, expected answers, golden/reference actions, grading/reward data, and semantic equivalents
at any path are evaluation-only. Runtime agents, prompt builders, knowledge indexes, application data
loaders, and APIs are default-deny consumers. Source code, examples, simulations, renamed paths, and
every other unclassified upstream artifact are also denied unless a later reviewed specification
explicitly allow-lists them.

## Recovery and Verification

Invalid existing or foreign state is preserved. Resolve it manually after reading the categorized
diagnostic; do not point production commands at an alternate source or delete state automatically.
Use the quickstart's locked environment, tests, inspection, Git-ignore audit, and CI matrix to verify
the integration.

Feature 001 ends at acquisition, pinning, validation, inspection, attribution, and policy. It excludes
chunking, embeddings, database import, runtime agents, APIs, containers, and benchmark evaluation.
