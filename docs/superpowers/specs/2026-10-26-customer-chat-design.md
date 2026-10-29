<!-- Defines the approved customer chat approach and the local integration boundaries. -->

# Customer Support Chat Design

The user selected a polished banking customer experience with live OpenAI answers,
approved reuse of the existing key, and instructed implementation of the recommended
branded page plus Chatwoot widget. The existing knowledge engine remains authoritative
for retrieval, policy checks and durable conversation execution.

## Approach

Use React, strict TypeScript and Vite for the branded support page, with the native
Chatwoot widget for messaging and the Chatwoot dashboard for human agents. A custom
React messaging client was considered but adds history, delivery and handoff UI work
without changing answer quality. The native widget is the selected first increment.

Serve built frontend assets from the existing FastAPI process. The browser receives
only the Chatwoot origin and public website token from `GET /chat/config`; it never
receives OpenAI keys, Chatwoot API credentials or demo bearer tokens. The page must be
responsive, accessible, keyboard usable, and honest when chat is unavailable. It must
identify the synthetic banking demonstration without pretending to operate real accounts.

## Integration

- Chatwoot 4.19.1 supplies the customer widget and human inbox.
- A verified signed webhook accepts bounded incoming message and status events for
  exactly the configured account/inbox. Ignore private and outgoing messages.
- Persist normalized events before acknowledgement and deduplicate stable message IDs.
- Map external conversations to isolated server-owned VerityCX conversations using
  durable mapping rows and stable internal request keys.
- A bridge consumes events and publishes completed answers through Chatwoot APIs;
  the existing worker executes the OpenAI knowledge workflow.
- Use separate, versioned integration migration/state so applied Feature 002 migrations
  remain immutable. Integrate retention/deletion through cascading foreign keys.
- Check current Chatwoot ownership before bot processing/publication. Hand off through
  Chatwoot `open`, preserve a bounded summary, and resume only after authoritative bot
  ownership (`pending` with an actual AgentBot assignment) has been re-established.
  Unassigned pending status cannot authorize work or resumption. A customer message
  cannot claim ownership. Disable customer conversation resolution on the owned widget
  at the server as well as in its UI settings.
- Persist publication attempts before HTTP calls. Reconcile uncertain delivery using
  stable message metadata; never blindly retry a possibly successful message POST.
- Use a private account user API token for remote reads/reconciliation and a separate
  AgentBot token for message creation. The pinned bot token cannot read message history.
- No webhook payload, raw provider exception or credential may reach application logs.
- Preserve the original standalone conversation API and disconnected escalation semantics.

## Setup and Live Execution

Provide maintained scripts for frontend build, app/service startup, and optional local
Chatwoot provisioning. Use an isolated named Docker Compose project and separate
Chatwoot PostgreSQL/Redis storage; never reuse VerityCX tables. Keep services loopback
only. Generate local credentials privately and preserve them on rerun. The existing
OpenAI key remains server-side; preserve the existing model snapshot initially.

The environment initially had no Docker runtime or passwordless sudo access. The user
subsequently authorized installing Docker. Native WSL administrator access through WSL
management enabled installation of Docker Engine 29.9.2 and Compose 5.6.1 without changing
the user's password or sudo policy. The actual Chatwoot 4.19.1 stack is now running;
widget/handoff/resume smoke checks passed. On 2026-10-28, the updated private dotenv key
was accepted after the stale exported key was removed from the app launch environment.
A disposition-specific structured-output schema correction enabled a cited live answer
through the real widget. The full live matrix and human grounding review remain open.
Never replace unavailable dependencies with fake chat.

## Verification

Verify frontend build/type checks, configuration privacy, signature/timestamp validation,
event deduplication, ownership isolation, uncertain delivery, handoff/resume and restart
behavior. Run the existing offline suite sequentially. Perform a bounded live OpenAI
smoke check with synthetic policy questions using the approved existing key. Exercise
the actual widget and inbox when Chatwoot is available; otherwise report that gate open.
