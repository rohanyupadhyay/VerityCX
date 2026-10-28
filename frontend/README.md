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
- `tests/` verifies configuration validation, privacy, readiness, failures, late
  responses, and page behavior in jsdom without contacting Chatwoot or OpenAI.

The only application request is the same-origin, credential-free `GET /chat/config`:

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

Dependencies are pinned in the root package manifest and lockfile. The native SDK
contract follows the [official Chatwoot SDK guide](https://www.chatwoot.com/hc/user-guide/articles/1677587234-how-to-send-additional-user-information-to-chatwoot-using-sdk).
