<!-- Defines planned local settings, management commands and metadata-only observability. -->

# Configuration and Operations Contract

## Nonsecret Configuration

`config/support.toml` is a closed schema with documented defaults. Commands run from the Git root;
paths resolve against that root, not the caller's incidental working directory.

| Setting | Default / validation |
| --- | --- |
| provider | deterministic; enum deterministic/openai, no silent fallback |
| model | gpt-4.1-mini-2025-04-14; explicit snapshot for live mode |
| corpus_mode | synthetic; enum synthetic/official; customer cannot set it |
| bind / port | 127.0.0.1 / 8000; public binds rejected in 002 |
| worker_concurrency | 10, maximum 10 |
| pool_max_size | 20 per process |
| lease_seconds / heartbeat_seconds | 30 / 5, fixed reviewed defaults |
| work_scan_seconds | 1, same in normal and acceptance runs |
| processing_seconds / provider_attempts | 60 / 2, product limits |
| message_chars / conversation_messages | 8000 / 100, product limits |
| retention_days / purge_interval_seconds | 30 / 3600 |
| traces_enabled | false; opt-in explicit metadata exporter |

Runtime configuration errors fail startup with safe key/category only. Secret values and raw
configuration objects never appear in logs. The implementation must add ignore entries for
`.cache/support/` and local secret files before generating them. No change to existing acquisition
configuration or its environment policy is needed.

## Environment Inputs

- `VERITYCX_DATABASE_URL`: runtime-role DSN to the dedicated local support database.
- `VERITYCX_MIGRATION_DATABASE_URL`: optional administrative DSN used only by explicit migrations;
  it must not enter API/worker configuration.
- `VERITYCX_AUTH_FILE`: ignored local file mapping synthetic principals to hashed high-entropy
  tokens. Management can issue a raw token once into a separate ignored client credential file.
- `OPENAI_API_KEY`: required only for live provider mode.
- `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`: required only for explicitly enabled metadata export.

Use inherited local credentials or interactive secure setup; no secrets in CLI arguments, source,
specs or process output. A driver/SDK may see its necessary credential, but provider requests never
contain database or support tokens. Do not scan arbitrary user credential stores.

## Planned Entry Points

| Root command | Contract |
| --- | --- |
| uv run python scripts/manage_support.py db migrate | Apply versioned/checksummed application migrations and checkpoint setup using explicit admin DSN. Never reset/drop user databases. |
| uv run python scripts/manage_support.py auth init-demo | Create two synthetic principals and ignored client credential files; refuse overwrite; print paths only. |
| uv run python scripts/manage_support.py corpus prepare --mode synthetic | Build pending fixture manifest/index; print hash and safe summary. |
| uv run python scripts/manage_support.py corpus prepare --mode official | Require valid acquired checkout; prepare only approved document corpus. |
| uv run python scripts/manage_support.py corpus approve --hash HASH | Verify unchanged pending manifest and eligible sources, then activate it; no allow-list expansion. |
| uv run python -m veritycx.service.main | Start local API with required loop policy and shutdown handling. |
| uv run python -m veritycx.orchestration.worker | Start bounded work/recovery and hourly maintenance loops. |
| uv run python scripts/manage_support.py db purge-expired | Run idempotent eligible cleanup with runtime role; report aggregate counts only. |
| uv run python scripts/validate_support.py --suite offline | Exercise implemented API/worker with synthetic provider and dedicated test DB. |
| uv run python scripts/validate_support.py --suite grounding --live | Run frozen 40-case live synthetic grounding set; leave human rubric review explicitly pending. |
| uv run python scripts/validate_support.py --suite demo --live | Demonstrate official-document answer, follow-up after restart and truthful pending escalation. |

The literal HASH in the approval command must be replaced with the generated digest. These are
implementation contracts, not commands available at planning time. API and worker accept the optional
`--provider deterministic|openai` and `--corpus-mode synthetic|official` flags, overriding only those
nonsecret settings. Manifest activation is per corpus mode. Validation drivers select synthetic
mode for offline/grounding and official mode for demo; `--live` explicitly selects the live provider.
Administrative commands return
0 on success and 1 for categorized expected failure, with no raw source bodies, tokens or DB errors.
Validation returns nonzero for unmet automated gates; live grounding execution alone cannot mark
human review passed.

## Audit and Export

Persist acceptance audit with each accepted turn and final outcome with its result. Required local
fields: random correlation UUID, turn association, route (pending until decided), outcome, source IDs,
elapsed milliseconds and optional failure category. Model/snapshot, prompt version and nullable usage
support reproducibility. Rejected input logs only category/correlation, never request content.

The exporter constructs a new allow-listed metadata object: random per-turn correlation, route,
outcome, source identifiers, duration, category, provider/model and usage. Exclude owner and
conversation IDs, message/document bodies, escalation summaries, headers and raw exceptions.
Disable ambient auto-tracing regardless of inherited tracing environment; only the explicit
metadata exporter may send. Test child spans, failures and serializer fallbacks with intercepted
payloads. An exporter failure increments sanitized local metrics but does not change customer results.

After deletion/expiry local audit and operation records are purged with content. Exported anonymous
metadata follows the selected external project's retention; no claim is made that deleting a local
conversation erases a remote event. Real-user data and production retention require a later review.
