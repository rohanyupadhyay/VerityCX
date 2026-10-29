<!-- Documents the isolated Chatwoot runtime, private provisioning and local acceptance gate. -->

# Local Chatwoot setup

The customer page uses the native Chatwoot widget. Chatwoot supplies the agent dashboard,
website inbox and human handoff; VerityCX supplies grounded answers through a signed AgentBot
webhook. The maintained [setup helper](../scripts/setup_chatwoot.py) provisions Chatwoot
**v4.19.1**, a synthetic local administrator, an account, a website inbox and an active
VerityCX AgentBot. [The Rails bootstrap](../scripts/chatwoot_provision.rb) uses Chatwoot's
application models in a transaction. No manual SQL, API token copying or existing account
adoption is needed.

## Runtime requirements

Use a Linux Docker Engine and the Docker Compose v2 plugin, running in the **same Linux
host network namespace as the VerityCX API**. Ubuntu 24.04 under WSL2 is supported when
Docker Engine runs inside that distribution. The helper never installs Docker, invokes
sudo or asks for a password. Docker daemon access must already work for your user.

The [Compose configuration](../config/chatwoot.compose.yml) uses Linux host networking so
Chatwoot's background worker can call the API at
`http://127.0.0.1:8000/integrations/chatwoot/webhook`. Rails binds only `127.0.0.1:3000`;
its dedicated PostgreSQL and Redis bind `127.0.0.1:55433` and `127.0.0.1:6380`.
Keep the VerityCX API on `127.0.0.1:8000`. No application listener needs a public bind.
These three Chatwoot ports must be available on the first start.

Docker Desktop requires its opt-in **host networking** setting (Docker Desktop 4.34 or
later, Linux containers). Standard bridge networking or an unset Desktop host-network
setting cannot deliver this loopback callback. Desktop's host network is distinct from
a native WSL Engine: verify that the Chatwoot worker can reach the WSL distribution's API
before accepting the deployment. Use native Docker Engine in the API's distribution if
that callback is unreachable. Do not change the API bind to `0.0.0.0` as a workaround.
See [Docker's host network requirements](https://docs.docker.com/engine/network/drivers/host/).

## Commands

From the repository root, inspect the current runtime without creating files or starting
services:

```bash
uv run python scripts/setup_chatwoot.py --check
```

A machine without Docker reports `chatwoot_docker_missing` and exits 1. A daemon permission
or connectivity failure reports `chatwoot_docker_unavailable`. Neither creates credentials,
alters the app environment or attempts privileged installation. A successful check verifies
owned resources, saved integration settings and running services, including the configured
container health checks. It does not prove webhook delivery or answer quality.

Optionally prepare private files **without Docker**:

```bash
uv run python scripts/setup_chatwoot.py --prepare --allow-local-webhooks
```

After Docker is available, provision and start the complete local deployment:

```bash
uv run python scripts/setup_chatwoot.py --allow-local-webhooks
```

The explicit `--allow-local-webhooks` flag is required because
[Chatwoot v4.19.1 SafeFetch](https://github.com/chatwoot/chatwoot/blob/v4.19.1/lib/safe_fetch.rb)
rejects private-network webhook destinations by default. The helper sets the upstream
`SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` variable **inside this isolated local Chatwoot
instance**. This allows private-network fetching generally within Chatwoot; it is not a
single-endpoint exception. Use it only for this trusted local synthetic demonstration,
with all services bound to loopback. The helper neither changes the existing API's URL
validation nor modifies any external Chatwoot instance. Do not expose this configuration
as a public or shared production service.

The helper pulls pinned application, PostgreSQL/pgvector and Redis image versions, starts
the dedicated database and Redis, executes `db:chatwoot_prepare`, provisions the local
resources through Rails, then starts Rails and Sidekiq. First startup can take several
minutes. Captured operational output stays in the private setup log; terminal output
contains only safe status categories and the private directory path.

Restart the VerityCX API and worker after provisioning so they load the new integration
settings. After filling the private app settings, the helper runs the maintained
`manage_support.py db migrate` command to apply the VerityCX integration schema.
Chatwoot's own database preparation never migrates application tables. Build the customer page using the repository frontend build command before
serving it through the API.

## Private files and reruns

Default generated files live under the ignored `.cache/support/chatwoot/` directory
(mode `0700`), with files mode `0600`:

- `credentials.json`: stable local administrator email/password, database/Redis passwords,
  Rails secret and installation ownership identifier.
- `compose.env`: private container configuration. Do not source it as a shell script.
- `integration.json`: actual account/inbox IDs, public website token, local administrator
  API access token, AgentBot access token and AgentBot signing secret.
- `setup.log`: private Docker and Rails diagnostics; it may contain credentials.
- `.veritycx-chatwoot`: installation ownership marker.

Open the Chatwoot dashboard at `http://127.0.0.1:3000` and use the local administrator
credentials in the private credentials file. The email is synthetic and no confirmation
email is required. The helper does not print the password. Do not share the private files
or attach the setup log to issues.

Successful provisioning fills exactly these settings in the root `.env`, preserving
comments, unrelated values and the existing OpenAI key/model:

```text
VERITYCX_CHATWOOT_URL
VERITYCX_CHATWOOT_ACCOUNT_ID
VERITYCX_CHATWOOT_INBOX_ID
VERITYCX_CHATWOOT_WEBSITE_TOKEN
VERITYCX_CHATWOOT_API_TOKEN
VERITYCX_CHATWOOT_BOT_TOKEN
VERITYCX_CHATWOOT_WEBHOOK_SECRET
```

Only the Chatwoot URL and website token belong in browser configuration. The private API
token belongs to the provisioned local administrator and supports conversation reads and
reconciling uncertain deliveries. The separate bot token publishes replies as the AgentBot;
Chatwoot v4.19.1 does not allow bot tokens to read conversation message history. Both tokens
remain server-side and are reused on reruns. The webhook secret is the actual AgentBot secret generated by
[Chatwoot's WebhookSecretable concern](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/models/concerns/webhook_secretable.rb).
[The pinned webhook implementation](https://github.com/chatwoot/chatwoot/blob/v4.19.1/lib/webhooks/trigger.rb)
signs the timestamp and exact JSON body. The provisioner does not invent a separate secret.

Rerun the same setup command to reuse the account, inbox, bot, volumes and credentials.
Nonempty conflicting app/container values, missing saved credentials, redirected files,
unmarked directories, mismatched Docker resource labels or an unrelated existing admin
cause a safe failure. The helper never resets a password to recover lost files. Preserve
the private directory together with the Docker volumes. A custom `--root` must be an
absent directory on first preparation, and must be kept out of version control.

The fixed Compose project is `veritycx-chatwoot`. Its PostgreSQL database is
`veritycx_chatwoot`, with separate `veritycx-chatwoot_postgres_data`,
`veritycx-chatwoot_redis_data` and `veritycx-chatwoot_storage_data` volumes. It never uses
VerityCX's application/test database or their tables. Setup checks both the Compose project
label and a per-installation ownership label before touching existing resources. No reset,
drop, volume deletion or adoption command is provided.

To stop services while preserving volumes and private credentials:

```bash
docker compose --project-name veritycx-chatwoot \
  --env-file .cache/support/chatwoot/compose.env \
  --file config/chatwoot.compose.yml stop
```

Use the helper again to restart. Shell environment overrides can affect a manually invoked
Compose command; the setup helper removes conflicting Compose variables from its child
environment. Do not run `docker compose config` or dump container environment settings into
shared logs, because the expanded configuration contains secrets.

The helper disables the website channel's server-side `end_conversation` flag on creation
and on owned-inbox reruns, preserving every other widget feature flag. This prevents the
customer widget's status-toggle endpoint from resolving a conversation during human
handoff; hiding the button in the customer page alone is insufficient. The pinned
[widget controller](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/controllers/api/v1/widget/conversations_controller.rb)
checks this channel flag before allowing the status change.

To return a handed-off conversation to automated support, staff must explicitly assign it
to the **VerityCX knowledge assistant AgentBot**. Chatwoot's
[conversation assignment service](https://github.com/chatwoot/chatwoot/blob/v4.19.1/app/services/conversations/assignment_service.rb)
sets the bot assignment and pending status together under a lock. Merely setting a
conversation's status to `pending` does not establish bot ownership and cannot resume
VerityCX replies. Customer messages also cannot establish that ownership.

This setup supports one AgentBot in its owned account. The provisioner rejects a conflicting
bot, but the bridge checks assignment type rather than the specific bot ID. Do not manually add
another bot to this account: assigning a conversation to it could also authorize VerityCX replies.
Exact bot identity binding is required before supporting shared accounts with multiple bots.

## Acceptance and current limitation

Offline verification:

```bash
uv run pytest tests/support/contract/test_chatwoot_setup.py
```

The original development environment had no Docker executable or passwordless sudo.
After user authorization on 2026-10-27, Docker Engine 29.9.2 and Compose 5.6.1 were
installed through native WSL administrator management. Docker is enabled at WSL startup,
the developer belongs to the Docker group, and normal-user container execution passed.
All four owned services now run with separate persistent volumes. The actual Rails
provisioning and migrations succeeded, including its server-side widget flag assertion.

A real browser smoke check passed customer widget readiness and opening, signed inbound
message delivery, open human handoff with private summary, staff API reply delivery into
the widget, explicit AgentBot reassignment and a resumed policy refusal. The staff reply
was sent by the automated local check as the owned demo administrator; it does not mean
a human reviewed the case. No paid model was used for that workflow.

On 2026-10-28, the replacement OpenAI key was accepted. A response-schema mismatch was
fixed by separating cited answer claims from clarification/abstention text; three real-SDK
offline regression cases cover those variants. The app and worker were restarted with
the stale exported key removed from their launch environment so the replacement in root
`.env` could load. Explicit environment values still take precedence over dotenv.
The actual customer widget then received exactly one live AI answer: the synthetic Birch
checking monthly fee is 5 synthetic dollars, citing `policy-02:0001`. There were no browser
page errors. This smoke check does not complete the full live matrix or human rubric review.

For complete acceptance, verify the customer page loads the real widget, a synthetic policy
question receives one grounded bot answer, a handoff appears as an open conversation in
the human inbox, a human reply reaches the widget, and the bot remains silent until an
agent explicitly assigns the conversation back to the VerityCX AgentBot. Verify that the
customer cannot resolve a handed-off conversation and that pending status alone does not
resume bot replies. Repeat after restarting the API, worker and Chatwoot services. These checks exercise real webhook delivery, including the host network
and SSRF settings; do not substitute fake responses when Chatwoot is unreachable.
