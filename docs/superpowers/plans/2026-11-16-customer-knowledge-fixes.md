<!-- Defines fixes for failures observed in the live official-corpus chat smoke test. -->

# Customer Knowledge Fixes

The user requested fixes for the observed live failures: staff-only document exposure,
personal/business product mixing, incorrect citations rejected as invalid output, stale
synthetic homepage examples, and weak product discovery.

## Design

- Exclude explicitly staff-only documents from the prepared manifest, index, public pages,
  and chat. Validate excluded files and reject source tampering. An old unsafe manifest
  must fail validation until this maintenance operation explicitly prepares and approves
  its replacement. Keep the exact upstream checkout unchanged.
- Derive product families and categories from structured source identifiers, with title
  rules as fallback. Match named products conservatively; preserve longer product modifiers
  and business/personal distinctions. Unknown named products abstain rather than borrowing
  another product's facts. Follow-ups use the rewritten standalone product reference.
- Prefer distinct product-family overview documents before secondary detail documents in
  category discovery, within existing evidence and related-source budgets.
- Constrain answer citations to selected section IDs in the remote schema while preserving
  independent publication validation and the existing attempt budget.
- Use source-independent homepage examples instead of fictional fixture product names.

## Implementation and verification

- [x] Source audience regression tests, filtering, and denial through public routes.
- [x] Product isolation, unknown-product, longest-name, and discovery regression tests.
- [x] Provider citation regression and exact saved-request live checks.
- [x] Homepage regression, frontend tests/typecheck/build.
- [x] Prepare and approve corrected official/synthetic corpora; restart the app.
- [x] Repeat live widget/API cases, verify sources and internal denial, and run static and
  offline suites against the final files. Keep raw upstream content and credentials out
  of maintained artifacts.

## Final verification

- Offline Python suites: 626 database-free tests and 124 dedicated PostgreSQL tests passed.
  Four marked live tests were excluded. Both suites retain the existing Starlette/AnyIO
  deprecation warning. Earlier failures from the superseded corpus identity and mixed
  in-flight code versions were resolved by updating the reviewed comparison identity and
  rerunning against unchanged final files.
- Frontend: 34 tests, TypeScript checking, production build, and Prettier checks passed.
  Ruff lint/format, strict mypy across 183 files, changed Markdown checks, environment
  contract, and whitespace checks passed.
- Explicitly reapproved the corrected official corpus with 639 customer-facing documents
  and the unchanged 40-document synthetic fixture corpus. Restricted direct lookup returns
  404\. Repeated official initialization preserves corpus file bytes and modification times.
- Live API checks verified personal savings facts and follow-up isolation, Blue Account
  requirements, five distinct cited card products, punctuated names, lowercase unknown
  modifiers, business constraints, absent fixture products, internal-code abstention, and
  unavailable banking operations. No internal codes are retained in this record.
- The actual customer widget returned cited Blue Account facts and resolved its follow-up
  to the same product. The homepage now uses corpus-independent questions and descriptions.
- Independent review found product-scoping edge cases; authored failing-then-passing tests
  cover ordinary card phrasing, original audience constraints, punctuation, title variants,
  longest names, and both capitalized and lowercase unknown modifiers.

These bounded live checks establish the observed fixes, not exhaustive semantic correctness
over all customer-facing policies. Product overviews retain the existing bounded evidence
budget and explicit incomplete-list note.
