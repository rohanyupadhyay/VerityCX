<!-- Documents authored synthetic policy fixtures and their explicit nonproduction scope. -->

# Synthetic documents

These closed JSON documents are authored solely for deterministic control-flow tests and the later
40-question live grounding review. Twenty supported policies and ten conflicting policy pairs are
fictional; no banking or benchmark data is present. `grounding.json` in the parent directory freezes
questions, required facts and admissible section IDs. These facts are not financial advice or real
bank policies. Prepare/approve this fixed directory using root `scripts/manage_support.py` commands.
The corpus enumerator allows this documentation file but never indexes it. Tests run under
`uv run pytest tests/support/unit/test_corpus.py tests/support/unit/test_retrieval.py`.

## Current files

`conflict-01-a.json`, `conflict-01-b.json`, `conflict-02-a.json`, `conflict-02-b.json`, `conflict-03-a.json`, `conflict-03-b.json`, `conflict-04-a.json`, `conflict-04-b.json`, `conflict-05-a.json`, `conflict-05-b.json`, `conflict-06-a.json`, `conflict-06-b.json`, `conflict-07-a.json`, `conflict-07-b.json`, `conflict-08-a.json`, `conflict-08-b.json`, `conflict-09-a.json`, `conflict-09-b.json`, `conflict-10-a.json`, `conflict-10-b.json`, `policy-01.json`, `policy-02.json`, `policy-03.json`, `policy-04.json`, `policy-05.json`, `policy-06.json`, `policy-07.json`, `policy-08.json`, `policy-09.json`, `policy-10.json`, `policy-11.json`, `policy-12.json`, `policy-13.json`, `policy-14.json`, `policy-15.json`, `policy-16.json`, `policy-17.json`, `policy-18.json`, `policy-19.json`, `policy-20.json`.
