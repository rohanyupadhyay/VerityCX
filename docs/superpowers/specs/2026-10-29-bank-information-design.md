<!-- Proposes public bank information pages and shared search grounded in the active corpus. -->

# Bank information pages and shared search

Status: approved by the user on 2026-10-29. The user selected product pages
with shared search. Details below are proposed implementation choices, not further
decisions attributed to the user.

## Intent and scope

Visitors must be able to understand what the demonstration bank offers before
asking VerityCX a question. Replace the current experience, which names four help
topics but sends visitors to chat for their details, with browsable bank information
and shared search. Visitors can read the information even when chat is unavailable.

Publish every document in the server's active, approved banking knowledge corpus.
Do not claim that this corpus contains every fact about a real bank. The current
synthetic corpus contains 20 supported policies and 10 deliberately conflicting
pairs. Details such as interest rates, branch locations, eligibility rules, and
contact numbers must appear only when the source documents actually supply them.
Do not invent details to make the website appear complete.

Bank account records, credentials, conversations, evaluation tasks, and unclassified
upstream artifacts remain outside the public information contract. This feature
does not add banking transactions, change corpus approval, or change the chat engine.

## Approaches

1. A single searchable guide makes policies easy to find with relatively little
   navigation, but gives visitors less context about the different services.
1. Separate product and service pages provide that context, but without shared
   search visitors must already know where to look.
1. Product and service pages with shared search combine exploration and direct
   lookup. This is the recommendation the user selected.

Use the existing React, strict TypeScript, Vite, FastAPI, and Chatwoot setup.
No new hosting platform, content management system, AI provider, or paid API calls
are needed for this feature.

## Visitor experience

The home page introduces the demonstration bank, links to service pages, and offers
a clearly labelled search across all bank information. The existing support entry
points remain available. The main navigation identifies bank information and support.

Provide service pages for accounts, savings, cards, payments and transfers, deposits
and cash access, and other policies. Show a short factual introduction, the named
products or services represented in the sources, and links to their full policies.
Empty categories are omitted rather than filled with invented products.

Each policy has a linkable detail page with its source title and complete source
content. Display readable paragraphs and headings, preserving all substantive
information. Render document content safely as text; do not execute embedded HTML
or load assets from source content. Show the document identifier and corpus version
as source information without exposing filesystem paths.

The shared search matches titles and full document content, accepts ordinary
keywords such as "replacement fee" or "transfer cutoff", and presents titles,
matching excerpts, category labels, and detail links. It supports clearing the
query, paging results, a visible result count, and an explicit no-results state.
Search state belongs in the URL so navigation and sharing work. Search makes no
provider calls and does not store queries in application data or telemetry.

Offer contextual example questions with each policy, derived from its title, plus
an "Ask VerityCX" button. The button opens the existing native Chatwoot widget only
when ready. Do not imply that opening chat submits or prefills a question; show the
question visibly so the visitor can copy it. Keep the existing honest connection
state, human handoff guidance, and synthetic-demo disclosure.

Keep both conflicting source versions discoverable. The synthetic Zephyr policy
pairs receive a clear conflict notice and links to both versions; do not select one
as authoritative. For other corpora, preserve all documents and identify duplicate
titles as multiple sources without claiming automatic semantic conflict detection.

Retain the current visual language, mobile layouts, keyboard access, visible focus,
and reduced-motion behavior. Page navigation updates the page title and moves focus
to the main heading. Links, Back/Forward, direct visits, refresh, and unknown-page
handling must work without requiring a previous visit to the home page.

## Content and public contracts

Add read-only, same-origin public bank-information endpoints to the existing API.
The configured server corpus mode selects the source; visitors cannot supply a mode,
file path, or source root. Reuse the existing approved-manifest and verified-source
loading boundary on every request. Read full validated documents rather than
returning only the six sections used for chat retrieval.

Proposed contracts:

- `GET /bank/api/policies`: bounded search and category filtering, with a page of
  document identifiers, titles, categories, excerpts, total count, and corpus version.
- `GET /bank/api/policies/{document_id}`: a complete validated document and its
  corpus version, category, and any explicitly known related conflict identifiers.
- Frontend routes under `/bank`, including service pages, search, and policy details.

Implement pagination and limits explicitly; never silently omit source documents or
truncate the full policy detail. Reject malformed queries with a bounded validation
response and return 404 for unknown document identifiers. The builder may finalize
parameter names and numerical limits, with tests for those limits.

Keep category and conflict metadata separate from authoritative source text. For
the synthetic corpus, map its known document identifiers to the service categories
and conflict pairs. For official documents, use conservative title-based category
matching with an "Other policies" fallback; every document remains reachable and
searchable even without a category match. Do not copy upstream source documents into
tracked frontend files or change the active corpus to make the website work.

Unavailable, unapproved, or changed sources produce a sanitized 503 and a visible
information-unavailable state with retry. Do not silently fall back to fixture text
or display an old corpus as current. Reading policies is independent of Chatwoot
readiness and database availability. Website requests use no browser credentials,
and public responses contain no private configuration or internal paths.

Serve the frontend shell only for explicit supported page routes, preserving API
errors and existing authenticated routes. Update Vite development proxying so the
public bank API behaves the same in development and production. No database schema,
environment variable, or corpus-approval changes are planned.

## Affected areas and verification

The change touches the frontend page structure, styling, navigation, content loading,
and tests; public FastAPI routes and frontend serving; knowledge-document projection;
and their module READMEs. The implementer may choose component boundaries and a small
typed navigation helper or a routing dependency if necessary, documenting that choice.

Acceptance checks must establish:

- Every approved source document is reachable, including documents without category
  metadata and both members of conflicting pairs; full detail preserves source facts.
- Search matches titles and body text, category filters and pagination work, and
  empty, malformed, unknown-document, source-change, and unavailable states are honest.
- No private source, task data, credential, path, or unapproved document is published.
- Supported direct links, refresh, Back/Forward, keyboard navigation, and narrow
  mobile layouts work. Chat readiness and native-widget behavior remain intact.
- Frontend tests, type checking, formatting, and build pass; changed Python code
  passes the repository's linting, formatting, strict typing, and relevant offline
  contract tests. A browser check covers navigation, responsive layouts, and chat
  independence without requiring a paid provider call.

## Remaining decisions

No additional product decision is required to prepare an implementation plan.
The user must approve this design before implementation. Missing bank facts remain
absent until authoritative content is supplied; this feature cannot manufacture them.
