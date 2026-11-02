# RAG category retrieval: step 2 design

Status: proposed for user approval. Builds on the merged and activated
[step 1 design](./2026-10-30-rag-retrieval-step-1-design.md).

## Intent and confirmed decisions

Make broad category questions retrieve adequate coverage of the approved policies
already grouped on the bank information pages. The original cards question should
cover Cedar, Hazel, and Pine, including Pine's debit policy, which does not contain
the word card. Listing documented products must not imply an exhaustive product
catalogue or invent eligibility, benefits, or other missing facts.

The user selected these approaches on 2026-11-02:

- List products documented in approved policies, with citations and an explicit
  statement that the list may be incomplete. An authoritative offering catalogue
  is not required before giving this bounded answer.
- Extend the existing model rewrite output to identify category overviews. Do not
  add a separate classification call.

The remainder of this document proposes implementation choices for approval.
It covers all existing service categories; no new product taxonomy is introduced.

## Current behavior and approaches

[catalog.py](../../../src/veritycx/knowledge/catalog.py) already classifies full
documents for the bank pages. Synthetic policies have authored category assignments;
other titles use a conservative keyword classifier with Other policies as fallback.
The cards category contains policies 03, 08, and 16. Chat currently selects 03 and
08 through normalized lexical matching, and the answer model can abstain because
those fee policies do not establish a complete offering list.

Two approaches were considered:

1. **Extend the existing rewrite call, selected.** Return a validated category and
   overview intent alongside the standalone query. Reuse the bank-page classifier
   for document membership. This handles paraphrases and conversational context
   without an extra call, but classification remains model output and needs
   application validation and explicit grounding constraints.
1. **Detect intent with spaCy rules.** Recognize overview phrasing locally. This is
   deterministic but requires maintained linguistic patterns and more work for
   paraphrases and follow-ups. It was not selected.

Simply adding category words to every passage was rejected: it would broaden
focused questions and would not ensure coverage across documents.

## Scope and constraints

- English only; retain spaCy normalization and bounded NLTK/WordNet fallback.
- Reuse the existing six category keys and labels, including Other policies.
- Keep one rewrite call capped at ten seconds, at most two answer attempts, and
  the shared database-time sixty-second deadline. No hidden model calls or SDK retries.
- Keep at most six evidence sections, each at most 2000 characters, at most 12,000
  evidence characters, 16,000 prior-context characters, and 8000 output characters.
- Keep source bytes, parser behavior, section IDs, source roots, corpus approval,
  owner isolation, fencing, retention, citation checks, bounded inference capacity,
  and the passage-only cache.
- No embeddings, vector service, reranker, new language resource, private synonym
  dictionary, new UI, authoritative catalogue creation, or banking-record access.
- Broad evaluation remains step 3; selecting semantic-search upgrades remains step 4.

## Shared approved category snapshot

Use the existing full-document category_for function as the shared classifier for
both bank pages and corpus preparation. Do not classify passage headings: indexed
section titles can append headings that would change the bank page's category.

Introduce a version-3 corpus manifest containing a catalog index. Each entry stores
an approved document ID, its original document title, and its existing category key.
It must contain exactly one entry for every source document and no foreign IDs.
This index is discovery metadata; policy claims still require source passages.

Bind the index and a category-policy identity into the corpus hash. The policy
identity covers a reviewed policy version plus the shared labels, synthetic
assignments, title-classification data, and related-title grouping policy. Changes
to classifier behavior require advancing its policy version. Reconstruct and
verify the index against unchanged approved source bytes during manifest checks.

Version-1 and version-2 manifests retain their original hash rules and remain
available for historical verification and public document browsing. Freeze both
existing fixture hashes in regression cases. Existing lexical functions remain
available as baselines. The new chat runtime requires an explicitly approved
version-3 corpus whose NLP and category identities match the loaded implementation.

## Typed rewrite intent

Advance the rewrite prompt/schema version to 2. Its search result contains:

- query: the standalone question, preserving names, numbers, negation and constraints;
- scope: focused or category_overview;
- categories: distinct existing category keys, empty for focused searches and
  nonempty for category overviews, bounded by the six supported keys.

The clarification result is unchanged. Supply the available nonempty categories
and their labels as server-derived metadata to the existing rewrite call. Validate
closed keys, scope/category consistency, duplicate categories, bounds, and malformed
output. Category order is canonical server order, not model preference.
An existing category key remains valid even when no approved document currently
belongs to it; availability hints do not authorize searching a different category.

The model should choose an overview for questions such as card options or which
cards are documented, and focused for a named product's fee. Ambiguous references
still request clarification. Specific qualifiers such as business eligibility or an
unknown product must not disappear merely because a category can be identified.

All fields remain untrusted search metadata. They cannot authorize a source, create
a policy fact, change ownership, or supersede the original customer question.
Rewrite failures retain the existing clear retry message and never fall back to an
unresolved raw question. Bind the new request metadata and schema version into the
durable request digest; reserve once and reuse only a compatible successful result.
Extend the explicit offline adapter with authored overview cases, never as a live
failure fallback.

## Evidence selection

Focused searches keep the step-1 normalized lexical ranking and empty-result-only
WordNet fallback. They do not automatically add all documents in a category.

For category_overview:

1. Resolve eligible documents from the approved catalog index using the validated
   category keys. Retain original question and rewritten query for section ranking.
1. Group documents with the same case-folded original title, matching the bank
   pages' related-policy grouping. Keep source versions together rather than
   silently choosing one side of a known conflict.
1. Rank groups within each category by their best normalized lexical section
   score, breaking ties by stable document/section identity. Category membership
   permits selection even when that document has no lexical overlap, as with Pine.
1. Allocate groups across requested categories in canonical round-robin order.
   Start with one best section per document in a chosen group. A group must fit
   completely within the remaining section/character budget or be deferred intact.
1. After the coverage pass, fill remaining space from already represented documents
   using the existing normalized scoring and stable ties. Do not add an extra
   section that displaces an unrepresented group that would fit.

This preserves the six-section/12,000-character caps. Categories larger than the
budget return a partial selection, with coverage recorded honestly. Do not truncate
source text or merge many documents into an invented source section to bypass caps.
Empty categories abstain without searching unrelated categories or spending an
answer attempt. Category selection itself needs no WordNet expansion; focused
searches retain its current conditional behavior.

Record requested categories, eligible and represented document counts, and whether
some eligible documents were omitted. These counts describe source coverage, not
the number or completeness of products in the real bank's offering.

## Grounded answer behavior

Advance the answer prompt metadata to version 3. Supply selected policy passages
plus the bounded search scope and coverage metadata. The original question remains
authoritative; category membership and history remain discovery context, not policy facts.

For an overview, instruct the model to answer from products or services evidenced
by the selected policies rather than require an exhaustive catalogue. Each listed
product or policy claim still needs a selected-source citation. Do not infer that a
product has another card's fee or that all products share eligibility or benefits.
If qualifiers are unsupported, disclose the missing information or abstain instead
of answering a broader, easier question. Disclose conflicts without resolving them.

For a successful overview answer, the application also renders a fixed scope note:
“These products or services are documented in the approved policies; this may not
be a complete list of offerings.” Reserve its characters within the 8000-character
publication limit. The note is a statement about answer scope, not a new policy claim.
Do not add it to clarification, abstention, error, or ordinary focused answers.

The cards acceptance example must name Cedar, Hazel, and Pine, cite the corresponding
approved policies, and retain the scope note. The model may summarize only supported
details; a fabricated benefit or a claim of catalogue completeness is a failure.

## Persistence, recovery, and runtime

Add migration 003; never edit applied migrations 001 or 002. Extend the rewrite
prompt-version constraint to accept retained version 1 and current version 2.
Allow category as a retrieval mode in addition to primary, synonym, and empty.
Add bounded local scope/coverage diagnostics; old rows keep unknown metadata rather
than being falsely backfilled as measured category results. Preserve the existing
one-row-per-turn and six-selected-ID constraints.

Update the typed rewrite row and selection result accordingly. Every new diagnostic
write retains the current parent/fence guard, including empty retrieval. Rewrite
content stays subject to conversation deletion and expiry. Do not export query,
history, source bodies, private paths, or raw provider errors.

The graph verifies the version-3 source snapshot, invokes the existing durable
rewriter, dispatches focused or overview selection under the existing bounded
inference executor, records diagnostics, and invokes the existing answer ledger.
Lease renewal, cancellation accounting, readiness, and recovery remain unchanged.
Old conversations retain their recorded corpus identity and cannot be silently
rebound. No second rewrite is issued for a spent or incompatible request.

## Acceptance and verification

- Shared-category tests prove chat and the bank pages use identical assignments,
  including documents whose first passage has a category-looking heading.
- The original cards question selects all three card documents despite Pine's
  absent card token. Mocked schema tests cover the new intent; real-model testing
  separately checks the final list and citations.
- Focused Cedar queries retain focused ranking; overview expansion is not invoked.
  Missing history clarifies; topic changes do not carry the preceding category.
- All existing categories, multiple categories, empty categories, invalid keys,
  omitted fields, duplicate keys, unknown products, and unsupported qualifiers have
  focused regression cases. Classification mistakes must not grant factual authority.
- Large and multi-section categories stay within both budgets, maximize document
  coverage before extra sections, preserve stable ordering, and disclose partial scope.
- Related conflicting versions are selected as a whole group or deferred as a whole;
  no overview helper silently resolves the conflict or drops its counterpart.
- Frozen v1/v2 hashes, v3 mapping/policy drift, explicit approval, legacy-conversation
  rejection, additive migration checksums, retention, one-call recovery, fencing,
  and sanitized audit/export metadata have native and contract checks.
- Run the maintained cross-platform quality gates and complete offline/native suite,
  keeping the existing five-second deterministic p95 target unchanged. Record
  timing variability rather than treating one passing retry as proof of a guarantee.
- After explicit live-test authorization, use isolated test storage and the existing
  selected credential to check cards, a focused fee, a contextual follow-up, missing
  context, unsupported products, and unsupported qualifiers. Mocked and deterministic
  tests are control-flow evidence, not proof of live model fidelity.

## Rollout and decisions left to implementation

Prepare and review version 3 without activating it while implementing. Activation
is a maintenance action: stop owned workers, apply migration 003, approve the
reviewed corpus, restart, and begin new conversations. Public policy bodies remain
unchanged. No app migration, corpus activation, paid call, push, or merge is part
of approving this design unless the user separately authorizes that action.

The builder may settle helper names, file boundaries, query layouts, and test
fixture mechanics within these contracts. Proposed boundaries are catalog/schema
metadata, versioned manifest support, typed rewriting, bounded category selection,
answer publication, additive storage/runtime integration, and documentation.
No new dependency is proposed. A later plan will name exact interfaces and tests.

## Builder check

A fresh read-only software-engineering review found nothing important left
unanswered for implementation planning. No implementation or runtime change has
been made as part of this design review.
