<!-- Documents the branded customer support page and the public Chatwoot integration boundary. -->

# Customer support page

This module is the public, synthetic Verity banking support experience. React renders
the responsive support page; Chatwoot owns messaging, conversation history, and human
handoff. The page never implements an alternative messenger or fabricates answers.
The server's existing knowledge workflow supplies policy-grounded responses.

Run every command from the repository root, using Node.js 24 and npm:

```sh
npm ci
npm run dev
npm test
npm run typecheck
npm run format:check
npm run build
```

Vite development binds to loopback and proxies `/chat/config` to the FastAPI process
at `http://127.0.0.1:8000`. The production build writes only to the ignored root
`dist/chat/` directory. FastAPI serves its index at `/` and its static assets at
`/assets/`. Open the FastAPI page for an integrated production preview.

## Structure and interfaces

- `src/App.tsx` contains the branded page, accessible navigation, native chat launch
  buttons, honest connection state, and expandable policy guidance.
- `src/chat.ts` validates public configuration and bounds the native SDK lifecycle.
- `src/styles.css` contains local typography, responsive layouts, and reduced-motion
  and keyboard-focus styles. No font or CSS CDN is used.
- `src/main.tsx` mounts the app once; `index.html` supplies document metadata.
- `src/bank.ts` validates public policy responses and handles shareable search URLs.
- `src/BankPages.tsx` renders service discovery, policy search, complete policy text,
  known conflicts, source metadata, and contextual questions around the native widget.
- `tests/` verifies configuration validation, privacy, readiness, failures, late
  responses, and page behavior in jsdom without contacting Chatwoot or OpenAI.

The widget uses the same-origin, credential-free `GET /chat/config`:

```json
{
  "enabled": true,
  "base_url": "https://your-chatwoot.example",
  "website_token": "public-website-token"
}
```

When disabled, the server returns `enabled: false` and null public settings. No
OpenAI key, Chatwoot API token, webhook secret, or demo bearer token belongs in this
module, its environment, or its bundle. Public settings are validated and narrowed
before use. Only an HTTP(S) origin is accepted for the Chatwoot URL; credentials,
query parameters, fragments, and subpaths are rejected.

When configured, the page loads `<base_url>/packs/js/sdk.js` and initializes it with
only the public website token and base URL. File uploads are disabled. It waits for
`chatwoot:ready` before enabling launch buttons. It does not identify users, attach
account data, prefill messages, or log message content. Chatwoot itself may store a
conversation cookie and make requests to its configured server.

## Operational constraints

The configuration request and widget initialization have bounded timeouts. Invalid
configuration, network errors, an SDK error, or a widget that never becomes ready
produce a visible unavailable state. Reloading the page retries initialization.
The page never promises a human is online or that an account action was performed.
The footer identifies the synthetic demonstration, and the safety guidance asks
visitors to use invented examples without credentials or real financial data.

Chatwoot is a separately operated dependency. Configure the backend public website
token and reachable URL, and allow that origin in the deployment's Content Security
Policy. HTTPS pages require an HTTPS Chatwoot origin. The website inbox's allowed
domains must include the page's origin. The real widget, grounded provider answers,
and agent inbox require end-to-end acceptance against a reachable deployment;
jsdom tests cannot establish those properties.

## Bank information

The home page links to `/bank`, service pages under `/bank/services/{category}`, and
full documents at `/bank/policies/{encoded-document-id}`. Shared search uses
`/bank/search?q=...&category=...&page=...`; URLs support direct visits, refresh,
Back/Forward, and ordinary new-tab navigation. The six service categories are
accounts, savings, cards, payments, deposits, and other policies. Empty categories
are omitted. Full policies and search work even when Chatwoot is unavailable.

Pages fetch only the public `/bank/api/policies` list/search and document-detail
endpoints. The API returns current approved source text, category counts, and corpus
metadata. Browser responses are validated into closed typed envelopes. Queries are
not persisted by this application; they remain in shareable browser URLs. The existing
server access-log policy still applies to requested URLs. Requests omit credentials,
disable caching, time out after ten seconds, and are cancelled when navigation
changes. Old responses cannot replace the current page. Missing, changed, or
unapproved content shows an explicit unavailable state with retry rather than
fallback fixtures. Unknown policies show a missing-page state.

Source content is rendered as text with paragraph and heading presentation; embedded
HTML is never executed. Known synthetic conflict pairs retain both versions and a
conflict notice. Other duplicate titles show related-source links without asserting
that their contents conflict. Example questions are visible text; Ask VerityCX opens
the native widget without automatically sending or prefilling a message.

Vite proxies both `/chat/config` and `/bank/api` to the local FastAPI service.
Service/API contracts are documented in `src/veritycx/service/README.md`.

Dependencies are pinned in the root package manifest and lockfile. The native SDK
contract follows the [official Chatwoot SDK guide](https://www.chatwoot.com/hc/user-guide/articles/1677587234-how-to-send-additional-user-information-to-chatwoot-using-sdk).
