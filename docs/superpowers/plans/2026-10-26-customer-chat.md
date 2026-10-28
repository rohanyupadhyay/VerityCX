<!-- Tracks implementation of the customer support page, Chatwoot bridge and setup. -->

# Customer Chat Implementation Plan

**Goal:** Deliver a branded banking support page with Chatwoot messaging, live grounded
OpenAI answers and real human handoff when a Chatwoot server is available.

**Spec:** [Customer chat design](../specs/2026-10-26-customer-chat-design.md).

**Architecture:** Three independent units: a React/TypeScript/Vite frontend, a typed
PostgreSQL-backed Chatwoot adapter, and maintained provisioning scripts. Integrate them
with FastAPI and the worker after their interfaces are established.

## Interfaces

- `GET /chat/config`: `{enabled: boolean, base_url: string|null, website_token: string|null}`.
- `POST /integrations/chatwoot/webhook`: signed, bounded normalized durable event intake.
- Handoff configuration uses `VERITYCX_CHATWOOT_URL`, `VERITYCX_CHATWOOT_ACCOUNT_ID`,
  `VERITYCX_CHATWOOT_INBOX_ID`, `VERITYCX_CHATWOOT_WEBSITE_TOKEN`,
  `VERITYCX_CHATWOOT_API_TOKEN`, `VERITYCX_CHATWOOT_BOT_TOKEN`,
  `VERITYCX_CHATWOOT_WEBHOOK_SECRET`.
- Frontend build output lives under ignored `dist/chat/` at the repository root.
- Default standalone API, deterministic fixtures and test-only setup stay compatible.

## Tasks

- [x] Build responsive branded frontend, widget lifecycle, accessible unavailable states,
  strict TypeScript and repeatable root-level build/test commands.
- [x] Build signed webhook configuration/client/store/bridge, independent integration
  migration, deduplication, ownership gates and delivery reconciliation, with tests.
- [x] Build local Chatwoot Compose/provisioning helper with private idempotent setup,
  pinned images, loopback networking and safe missing-Docker diagnostics.
- [x] Integrate frontend routes and handoff supervision into API/worker; update environment
  contract, root setup/run scripts, module documentation and roadmap status accurately.
- [x] Run quality gates, full offline tests, actual browser checks and an independent
  review. Attempt bounded live OpenAI smoke checks and track unavailable external
  acceptance separately.

## Local verification

The full offline suite passed **421 tests** against native PostgreSQL on 2026-10-28,
including three real-SDK structured-output regressions and two corpus-update intake
regressions. Frontend Vitest
passed **16 tests**, and strict TypeScript, production build, formatting, Ruff, mypy,
Markdown/YAML, environment-contract, lockfile and whitespace checks passed. Browser
checks passed at 320, 390, 650, 768, 1024 and 1440 pixels with no horizontal overflow
or JavaScript page errors, correct unavailable chat controls, and working FAQ disclosures.
An actual mobile layout failure was reproduced before the responsive heading fix.
The built bundle was checked against the configured OpenAI key without displaying it;
no secret was found. One upstream Starlette/AnyIO deprecation warning remains in pytest.

## Review decisions

Pinned upstream source review exposed distinct AgentBot/user API privileges and a
customer-driven resolved-to-pending transition. Separate token roles and an actual
AgentBot assignment now gate operation; staff must explicitly reassign a handed-off
conversation. Terminal intake limits trigger confirmed human handoff without starving
previously completed answers. Regression coverage was added before each correction.

Pre-merge review also reproduced webhook creation-key conflicts after approving a new
corpus. Intake now recovers the original parent and its corpus from the creation ledger,
including interruption before mapping creation; two database regressions cover replay
and new-message acceptance. Multiple AgentBots in one account remain unsupported and
are explicitly documented as a deployment limitation.

## External acceptance gates

- [x] Run the actual pinned Chatwoot containers, widget and human inbox. On 2026-10-27,
  native Docker Engine 29.9.2 and Compose 5.6.1 were verified as the normal user. The
  real browser/widget smoke check passed signed webhook handoff, private summary,
  staff API reply delivery, explicit AgentBot reassignment and a resumed policy refusal
  without a paid model call. This does not replace the full security/restart matrix.
- [x] Demonstrate a successful live OpenAI answer. On 2026-10-28, the replacement key
  worked after removing the stale exported value from the app launch environment.
  Both a direct provider call and the actual customer widget returned the synthetic
  Birch checking monthly fee of 5 synthetic dollars with a policy citation. The widget
  received exactly one public bot answer with no browser page errors. Three offline
  real-SDK regression cases cover the corrected answer/clarify/abstain wire schema.
- [ ] Complete the full live matrix and human grounding review.

The replacement key is stored privately in root `.env`. Explicit process values take
precedence over dotenv, so a stale exported value must be removed when selecting a valid
replacement from local configuration. Neither key was displayed or committed.
