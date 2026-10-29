<!-- Plans the approved public bank pages, source-backed policy API, and shared search. -->

# Bank Information Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Help visitors discover bank services, read all approved policies, and ask informed questions in VerityCX.

**Architecture:** Add a public read-only projection of the active approved corpus to FastAPI. React renders service and policy pages with server-backed shared search, preserving native Chatwoot and using a small browser-history navigation helper.

**Tech Stack:** Existing Python 3.12/FastAPI/Pydantic and React/TypeScript/Vite; no new dependencies.

**Spec:** [Approved design](../specs/2026-10-29-bank-information-design.md).

## Global Constraints

- Publish every document in the server's active, approved banking knowledge corpus.
- Do not copy upstream source documents into tracked frontend files or change the active corpus to make the website work.
- Bank account records, credentials, conversations, evaluation tasks, and unclassified upstream artifacts remain outside the public information contract.
- Visitors can read the information even when chat is unavailable.
- Do not invent details to make the website appear complete.
- No database schema, environment variable, or corpus-approval changes are planned.
- Run commands from the repository root; document new interfaces and keep strict types.

## Review Focus

- Source drift between verification and reading: reject changed bytes rather than publish them (Task 1).
- Unknown titles and conflicting sources: retain all documents, with fallback categories and explicit known conflict relationships (Task 1).
- Deep links and malformed paths: refresh works on supported routes while APIs and unknown routes retain real errors (Task 1).
- Rapid navigation and delayed responses: an old response must not overwrite the current page (Task 2).
- Unavailable chat or policy service: browsing and chat fail independently with an accessible retry path (Task 2).

## File structure

- `src/veritycx/knowledge/catalog.py`: verified full-document loading and public category/conflict metadata.
- `src/veritycx/service/bank.py`: bounded public listing/search/detail routes.
- `src/veritycx/service/app.py`, `frontend.py`: route registration and explicit frontend deep links.
- `frontend/src/bank.ts`: validated public types, fetch boundaries, and URL navigation helpers.
- `frontend/src/BankPages.tsx`: service index, results, full policy details, and states.
- `frontend/src/App.tsx`, `styles.css`: shared navigation and existing homepage integration.
- Existing module READMEs, API/frontend tests, and `vite.config.ts`: documentation and integration.

### Task 1: Public approved-policy API and deep links

**Files:** Create `knowledge/catalog.py`, `service/bank.py`, and `tests/support/contract/test_bank_information.py`; modify `knowledge/configuration.py`, `service/app.py`, `service/frontend.py`, their READMEs, and `vite.config.ts`.

**Interfaces:**

- Produce `active_documents(mode: Literal["synthetic", "official"]) -> tuple[CorpusManifest, list[KnowledgeDocument]]`, revalidating the active manifest, content hashes, IDs, and section inventory.

- Produce `register_bank(app: FastAPI, mode: Literal["synthetic", "official"]) -> None`.

- `GET /bank/api/policies?q=&category=&page=1` returns `corpus_version`, `mode`, `categories` (key/title/count), `total`, `page`, `page_size=12`, and `policies` (id/title/category/excerpt/conflict_ids/related_ids).

- Query maximum: 200 characters; page range: 1–100000. Reject unknown query parameters. All query terms must match case-insensitive title/content; deterministic title/ID ordering.

- `GET /bank/api/policies/{id}` adds complete `content`; unknown IDs return 404. All responses use no-store.

- Frontend paths: `/bank`, `/bank/search`, `/bank/services/{known-category}`, `/bank/policies/{encoded-id}`. Reserved API paths cannot become HTML fallbacks.

- [ ] Write contract tests using a real temporary prepared/approved corpus. Assert all 40 authored synthetic documents can be paged, exact Birch full text, body search, fallback categories, conflict links, absent private fields, unapproved/drifted source 503, malformed query 422, unknown ID 404, no database dependency, and supported/unsupported deep links.

- [ ] Run `uv run pytest tests/support/contract/test_bank_information.py -q`; expect failures because bank routes do not exist.

- [ ] Implement the interfaces, exact source verification, safe excerpts, category metadata, and explicit shell routes. Use synchronous endpoints so filesystem verification runs off the async event loop. Keep full content as text and private paths out of responses.

- [ ] Update module READMEs and proxy `/bank/api` in Vite.

- [ ] Run new contract tests and existing customer-page/corpus tests; expect all pass. Run touched Python formatter/linter/type checks and commit as `feat: expose approved bank information and policy search`.

### Task 2: Bank pages, shared search, and chat integration

**Files:** Create `frontend/src/bank.ts`, `frontend/src/BankPages.tsx`, `frontend/tests/bank.test.ts`, and `frontend/tests/BankPages.test.tsx`; modify `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/tests/App.test.tsx`, and `frontend/README.md`.

**Interfaces:**

- Consume Task 1 API envelopes, validating untrusted JSON before storing it in typed state.

- Produce `BankPages({state, onOpen}: {state: ChatState; onOpen: () => void}): ReactElement` for `/bank` paths. Keep connection ownership in `App`.

- Shared links use normal same-origin URLs intercepted only for unmodified local navigation. Browser history, query strings, focus, document titles, direct detail links, and unknown routes must work.

- Use `AbortController`, bounded fetch timeouts, and cleanup to prevent stale page updates. Do not persist queries or load an alternate fixture corpus on failure.

- [ ] Write tests for schema rejection, search submission/clear/filter/pagination URLs, complete text with literal HTML, fallback/multiple sources, native chat readiness, failure retry, and stale responses after navigation. Update homepage tests to assert a usable information link with chat disabled.

- [ ] Run `npm test`; expect new tests to fail because the page modules do not exist or links are missing.

- [ ] Implement the validated client and routed bank views. Include service overviews, named source titles, source metadata, counts, excerpts, full text, known conflict links, example questions derived from titles, visible loading/errors, and no-results messaging.

- [ ] Replace homepage topic chat buttons with service links, add a bank-information entry and homepage search, retain the existing support content and native messaging lifecycle. Add responsive styles without a new UI library.

- [ ] Run `npm test`, `npm run typecheck`, `npm run format:check`, and `npm run build`; expect all pass. Commit as `feat: add bank service pages and shared policy search`.

### Task 3: Integration verification and review

**Files:** Update `docs/README.md`, the approved design status text, and this plan's completed checkboxes. Repair implementation issues only when verified by a regression test.

**Interfaces:** Consume the complete public API and compiled frontend from Tasks 1–2.

- [ ] Run the full offline Python suite, strict typing, linting, formatting, frontend suite/build, environment contract, and maintained Markdown checks.
- [ ] Start a disposable local preview against a temporary approved copy of the authored synthetic document corpus. Do not alter runtime corpus approval or require a provider/database connection. Verify homepage → service → full policy, body search, clear/no-results, direct refresh, Back/Forward, unavailable chat, and 390px mobile width in a real browser.
- [ ] Request one fresh whole-branch code review against this plan and design, including the Review Focus cases. Fix important findings with a failing regression test first and rerun relevant checks.
- [ ] Record evidence, commit documentation as needed, and report the implemented behavior plus any material limitation. Do not push, merge, publish, or start paid provider calls as part of this task.
