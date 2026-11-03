<!-- Documents pure contract and policy unit tests. -->

# Support unit

Pure contract and policy unit tests. The current files implement the cases and fixtures described below.
Only project-authored synthetic data belongs here. No upstream documents, evaluation answers,
credentials or generated evidence may be committed.

Run from the repository root with `uv run pytest tests/support -m "not support_db and not live"`
for database-free tests, or `uv run pytest tests/support -m "not live"` for full offline validation.
The latter requires native PostgreSQL 18.6 and `VERITYCX_TEST_DATABASE_URL` naming the dedicated
`veritycx_support_test` database; missing prerequisites fail instead of skipping.
Live tests are excluded by default and require separate explicit authorization.

Shared interfaces live in `tests/support/conftest.py`: synthetic identity/document factories,
a dedicated-database fixture and process ownership guards. Test teardown may dispose only records
or subprocess handles created by that test; it must never reset unrelated databases or kill by PID.

## Current files

`test_checkpoint_serialization.py`, `test_configuration.py`, `test_corpus.py`, `test_event_loop.py`, `test_models.py`, `test_retrieval.py`, `test_routing.py`, `test_safety.py`, `test_trace_privacy.py`.

`test_chatwoot.py` adds offline signed-webhook, public configuration, two-token HTTP
routing, strict AgentBot assignment and safe error contracts. Its mock transports never
contact an actual Chatwoot server or OpenAI. The webhook persistence test prepares and
approves a corpus in its own temporary cache, independent of local app setup or test order.

## Category retrieval checks

The category suites pin shared catalog assignments, frozen v1/v2 hashes, strict
scope contracts, document coverage, indivisible related versions and final-note
character limits. SDK transports are mocked. These checks verify contracts and
control flow; they do not establish live semantic grounding quality.

The retrieval regression suites validate the separate case/replay inventory,
literal evidence expectations, real raw-wording retrieval and conservative
per-boundary verdicts. Corrupted observations exercise missing/forbidden evidence,
false coverage, lost context, changed questions, invalid citations and budget
failures. Report tests cover private file ownership/permissions, non-overwrite,
stdout canaries and pending semantic acceptance. The combined multi-category
last-slot related-group case closes the earlier selector coverage gap.
