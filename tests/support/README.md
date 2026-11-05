<!-- Documents shared synthetic fixtures and guarded test resources. -->

# Support tests

Shared synthetic fixtures and guarded test resources. Cases cover strict models, authentication, migrations, guarded checkpoints, recovery, retention,
escalation/resume, trace privacy and thirty authored adversarial inputs. Deterministic document
injection tests establish bounded adapter/control behavior, not live-model injection resistance.
Only project-authored synthetic data belongs here. No upstream documents, evaluation answers,
credentials or generated evidence may be committed.

Run from the repository root with `uv run pytest tests/support -m "not support_db and not live"`
for database-free tests, or `uv run pytest tests/support -m "not live"` for full offline validation.
The latter requires native PostgreSQL 18.6 and `VERITYCX_TEST_DATABASE_URL` naming the dedicated
`veritycx_support_test` database; migration tests also require `VERITYCX_TEST_MIGRATION_DATABASE_URL`. Missing prerequisites fail instead of skipping.
Live tests are excluded by default and require separate explicit authorization.

Shared interfaces live in `tests/support/conftest.py`: synthetic identity/document factories,
a dedicated-database fixture and process ownership guards. Test teardown may dispose only records
or subprocess handles created by that test; it must never reset unrelated databases or kill by PID.

Run database suites sequentially against their dedicated database. A second worker can legitimately
claim another test's accepted jobs and invalidate a fault-hook experiment. Hosted and live acceptance
remain separate from local passing tests.

## Current files

`conftest.py`, `harness.py`.

The retrieval quality inventory adds 24 scenarios/31 turns alongside the unchanged
40-case grounding suite. Unit checks use the real pinned NLP/selector; native
checks use actual storage/worker processing and explicit replay adapters. Detector
tests intentionally omit Pine or remove history and require failed verdicts.
SDK mock transports cover the live branch without paid network access. Actual live
execution remains explicit and is not part of default CI. See
[fixtures](fixtures/README.md) and the
[command guide](../../scripts/README.md#retrieval-regression-validation).

## Live card-discovery acceptance gate

A passing offline suite does not establish that the real model answers customer
questions correctly. Before declaring a rewrite, discovery, or answer-generation
change fixed, run this separately with explicitly authorized API access and the
dedicated test database configured:

```text
uv run pytest tests/support/acceptance/test_card_discovery_live.py -m live -q
```

This invokes the actual configured rewrite and answer models through the durable
worker pipeline. No response is replayed or supplied by a mock transport. Three
fresh executions of the original card question must return an answer naming
Cedar, Hazel, and Pine and cite all three policy documents. Additional live cases
check paraphrased discovery, a contextual follow-up, a genuinely missing reference,
and unsupported product/business questions. Failures block acceptance; do not
replace them with an offline pass or retry until a favorable response appears.

The test writes private synthetic review evidence under
`.cache/support/evidence/retrieval-regressions/`. It is intentionally excluded from
default offline CI because it makes paid provider requests. Record its result
separately from offline test results, and verify the original question in a fresh
native Chatwoot chat before declaring the customer-visible issue resolved.
