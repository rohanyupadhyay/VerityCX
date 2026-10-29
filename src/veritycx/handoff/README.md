<!-- Documents the signed Chatwoot adapter, durable state and operational limits. -->

# Chatwoot adapter

This package connects Chatwoot **4.19.1** AgentBot webhooks to the existing support repository and
worker. Standalone API authentication, escalation acknowledgments and graph execution remain in their
existing modules.

## Integration

Load configuration with `load_chatwoot_configuration(env)` in [configuration.py](./configuration.py).
All seven fields must be configured together: `VERITYCX_CHATWOOT_URL`, `VERITYCX_CHATWOOT_ACCOUNT_ID`,
`VERITYCX_CHATWOOT_INBOX_ID`, `VERITYCX_CHATWOOT_WEBSITE_TOKEN`, `VERITYCX_CHATWOOT_API_TOKEN`,
`VERITYCX_CHATWOOT_BOT_TOKEN`, and `VERITYCX_CHATWOOT_WEBHOOK_SECRET`. Fully absent/empty configuration disables integration; partial or
invalid values fail with a sanitized category. Origins permit HTTPS or HTTP on loopback only. Privileged
tokens are excluded from representations and the public bootstrap response.

`VERITYCX_CHATWOOT_API_TOKEN` must belong to a Chatwoot account **user** authorized to read the configured
account and inbox. It authenticates conversation reads, status updates and message-history reconciliation.
`VERITYCX_CHATWOOT_BOT_TOKEN` must belong to the configured **AgentBot**; it authenticates outgoing message
creation, including private handoff summaries, preserving the bot as sender. Chatwoot 4.19.1 denies
message-history listing to AgentBot tokens, so these credentials cannot be substituted for one another.
The webhook signing secret is the AgentBot's separate `secret` field, not either API access token.

Call `register_chatwoot(app, configuration, pool_getter, corpus_mode=settings.corpus_mode)` from
[routes.py](./routes.py) to register `GET /chat/config` and `POST /integrations/chatwoot/webhook`.
Before enabling the bridge, run `migrate_chatwoot(admin_dsn, runtime_role)` from
[migrate.py](./migrate.py) **after** the core migration. This verifies the core schema, installs an
independent exact-checksum ledger and grants runtime DML without DDL or ledger writes. Migration 002
adds origin scoping; migration 001 remains immutable. Rows from an earlier originless installation
become eligible only after a verified new webhook safely identifies their original owner.

Supervise `run_bridge(pool, configuration, settings)` from [bridge.py](./bridge.py) alongside the normal
worker. The bridge requires at least **two** pool slots: one for its per-thread session advisory lock
and another for short transactions. Cancellation propagates and closes the HTTP client and advisory
lock. Remote requests use bounded response sizes, timeouts, no redirects, no ambient proxy settings and
no automatic mutation retries. The adapter never logs webhook content or provider exceptions.

## Durability and ownership

[events.py](./events.py) verifies `X-Chatwoot-Timestamp` and `X-Chatwoot-Signature` against the exact raw
body using HMAC SHA-256 over `timestamp.raw_body`, with a five-minute tolerance. Intake is capped at
64 KiB; retained customer text is capped at 8,000 characters. Private/outgoing events are ignored.
Incoming message IDs deduplicate durable events; status events are wakeups, never ownership authority.
Only the configured account and inbox are accepted.

[store.py](./store.py) maps origin/account/inbox/thread identity to isolated server-owned conversations.
Stable owner-scoped request UUIDs recover acceptance after a crash. Every retained event and outbound
intent ultimately cascades from the original support parent during retention purge. Intake creates a
parent before its event transaction; interruption between those commits can leave an empty parent
until another webhook recovers it or normal retention purges it. Existing parents are recovered from
the original creation ledger before intake, preserving their corpus binding after new documents are
approved. The currently active corpus applies only to newly created conversations; it never rebinds
an existing thread or changes core creation-idempotency checks.

The bridge reads live remote inbox, status and assignment before processing or publishing. `pending`
with an actual nonnull `AgentBot` assignee permits bot work; unassigned pending never does. New
Chatwoot conversations with an active inbox bot already receive that assignment. An observed human takeover durably suppresses existing
answers, including in-flight computation, so later return to `pending` cannot revive them. Human-owned
incoming messages remain in Chatwoot and cannot authorize internal work. A handoff opens the remote
conversation, confirms `open`, and publishes a bounded **private** summary to the staff inbox. It does
not forward the standalone acknowledgment claiming nobody was notified. A specific observed pause,
followed by authoritative `pending` **and explicit AgentBot assignment**, permits the existing
server-owned pause/revision resume operation. Staff must assign the AgentBot to return automation;
changing only status is insufficient. A customer closing and messaging again can produce unassigned
pending, which cannot authorize either intake or resumption.

Completed answers are projected and published before new intake is attempted. `busy` intake remains
queued. Terminal repository refusals, including the 100-turn `conversation_limit`, `incompatible_state`
and `idempotency_conflict`, request human attention through an explicit remote `open` status update.
The native Chatwoot customer message remains visible to staff. The durable event is ignored only once
open/human ownership is authoritatively confirmed; an ambiguous status update retains retryable intake.
This prevents one permanently refused message from blocking earlier completed results indefinitely.

Each message POST requires a committed one-way `ready` → `sending` intent. A crash or ambiguous response
leaves `sending`/`uncertain`; subsequent scans search up to 20 message-history pages using the stable
`content_attributes.veritycx_turn_id` marker. A found marker completes the intent. Absence leaves it
`uncertain`, requiring operator investigation; **no automatic repost** occurs. This favors avoiding
duplicate customer replies over automatic recovery of a genuinely failed message send. There is no
operator repair UI in this increment; inspect durable state administratively and resolve deliberately.

## Limits and verification

Supported deployments have one AgentBot in the configured account, as enforced by the local
provisioner. Ownership currently checks AgentBot assignment type and a positive ID, not equality
with a configured bot ID. Manually adding another AgentBot is unsupported: assigning it a pending
conversation can also authorize this bridge. Bind the exact bot identity before supporting multiple
bots or a shared hosted account.

Chatwoot's message POST API has no atomic ownership precondition. A human takeover between the final
remote GET and POST remains a bounded external race; database fencing prevents local replay but cannot
make those two remote calls atomic. A takeover that happens entirely between two remote observations
cannot be detected from current status alone. Messages handled by a human are retained in Chatwoot and
are not replayed into the bot's internal history when automation resumes. Remote Chatwoot retention and
deletion remain Chatwoot's responsibility; local cascading purge does not delete external threads.

Unit tests in [test_chatwoot.py](../../../tests/support/unit/test_chatwoot.py) exercise configuration
privacy, signature binding, bounded intake, actual ASGI routes, ownership responses, HTTP metadata and
safe errors with `httpx.MockTransport`. Dedicated PostgreSQL tests in
[test_chatwoot.py](../../../tests/support/integration/test_chatwoot.py) exercise migrations, cascade,
identity isolation, replay, reconciliation, takeover and actual graph handoff/resume. These require
explicit dedicated test DSNs and must run sequentially with other database suites. Real widget/inbox
acceptance still requires a reachable configured Chatwoot deployment.

Pinned source references:

- [AgentBot signing secret](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/models/agent_bot.rb)
- [Signed AgentBot dispatch](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/listeners/agent_bot_listener.rb)
- [Exact HMAC headers](https://github.com/chatwoot/chatwoot/blob/v4.19.1/lib/webhooks/trigger.rb)
- [Current ownership response](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/views/api/v1/conversations/partials/_conversation.json.jbuilder)
- [Pinned AgentBot endpoint authorization](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/controllers/concerns/access_token_auth_helper.rb)
- [Message creation API](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/controllers/api/v1/accounts/conversations/messages_controller.rb)
