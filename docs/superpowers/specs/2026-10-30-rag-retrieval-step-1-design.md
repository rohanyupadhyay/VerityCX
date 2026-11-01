# RAG retrieval correctness: step 1 design

Status: approved for implementation by the user on 2026-10-30. Implementation
evidence and bounded execution rulings are recorded in the accompanying plan.

## Intent and scope

Make ordinary English banking questions retrieve relevant approved passages,
including follow-ups whose subject occurs in preceding conversation turns.
The reported question, "What cards does VerityCX offers?", currently selects six
unrelated conflict passages through the word "does" while missing singular "card".
The existing corpus contains relevant Cedar and Hazel card policies and a Pine
debit policy. Relevant information exists; the current retriever fails to select it.

The user wants four separately delivered steps:

1. Basic retrieval correctness, including the conversational rewriting agreed here.
1. Connect chat retrieval to the existing service categories.
1. Broader retrieval-quality regression coverage.
1. Measure improvements before deciding whether semantic search is needed.

This document designs step 1. Focused regression and safety checks belong to this
step; the broader benchmark and category integration remain separate deliveries.
In particular, step 1 must recover relevant card passages but does not promise
complete category coverage or a complete inventory of products.

## Confirmed user decisions

- Support English only.
- Use spaCy and NLTK where each is best suited; do not build a private word dictionary.
- Use spaCy for normalization and NLTK/WordNet for synonym lookup when needed.
- Use model-based query rewriting with preceding conversation context.
- Rewrite every question entering RAG, including standalone questions.
- A rewrite failure or timeout returns a clear retry message. No original-query fallback.
- Run synonym expansion only if primary normalized retrieval returns no evidence.
- A later answer-model abstention does not automatically trigger another search.
- Give rewriting a separate model setting, initially defaulting to the answer model.

The existing authority and intent router still acts on original customer input.
Requests routed to human assistance or unavailable operations do not become RAG
requests, and rewritten text never changes routing or authorizes capabilities.

## Approaches and choice

The conversation considered a narrow custom plural normalizer, Snowball stemming,
spaCy lemmatization, and NLTK lexical processing. The user preferred reusable NLP
libraries and selected spaCy plus NLTK/WordNet according to task suitability.
The user also selected rewriting every RAG question over detecting follow-ups,
explicit failure over raw-query fallback, conditional synonym lookup over
unconditional expansion, and independent rewrite-model configuration.

Proposed implementation: retain the bounded lexical ranking baseline, improve its
input representation, and add an explicit durable rewrite stage. Do not introduce
embeddings, a vector database, a second ranker, automatic web fetching, or a new
banking data source in this step.

## Request flow and outcomes

Original message and authorized completed history -> durable model rewrite ->
spaCy normalization -> primary lexical retrieval -> WordNet fallback only if
primary selection is empty -> existing grounded answer generation and validation.

The answer provider receives the original question, recent history, selected
original passages, and the rewritten search query as a distinct untrusted field.
The rewritten query supplies retrieval intent, never policy evidence.

Example: a preceding discussion of Cedar followed by "What is its replacement fee?"
becomes a standalone search query about the Cedar card replacement fee.
If multiple products remain plausible, rewriting returns a clarification question.
Do not choose an arbitrary product or infer policy facts from previous model text.

Proposed rewrite result is a closed, discriminated search-or-clarify envelope.
Search contains a nonempty query of at most 8,000 characters. Clarify contains
nonempty customer text of at most 800 characters. Both forbid unknown fields,
tools, evidence assertions, routing directives, and owner identifiers.
The rewrite prompt preserves names, numbers, negation, and constraints; it resolves
references using only the supplied history. Structural validation does not prove
semantic fidelity, so fidelity and ambiguity require explicit tests and live review.

Technical rewrite failures publish:

> We couldn't prepare your question for search. Please try again.

Record a sanitized rewrite-specific failure category. Failed rewriting does not
invoke retrieval or the answer provider. Successful clarification also stops before
retrieval. Empty evidence after the optional synonym pass retains the existing
honest abstention behavior; it is not a technical retry.

## Normalization and primary ranking

Proposed normalizer:

- Load the English spaCy pipeline once per worker, retaining only components
  required for contextual POS tagging and lemmatization. Do not activate NER,
  parsing, or vector similarity merely because the library provides them.
- Apply the same representation to original question terms, rewritten query terms,
  document titles/headings, and passage bodies. Batch passage normalization.
- Case-fold ordinary terms and use lemmas. Preserve product-name surface forms
  and numeric constraints; retain original text without modification.
- Start with spaCy's English stopword data and document project overrides.
  Common auxiliary/question words such as "does" must not supply relevance.
- Preserve negation and comparison constraints for interpretation, but do not let
  constraint-only input produce evidence through common negation words alone.
- Combine meaningful original and rewritten query concepts so rewriting cannot
  silently discard all original product or constraint terms.

Keep each normalized query concept unique. Use the existing log-weighted overlap
formula over the union of normalized title/heading and body terms, counting a term
once per section even if it appears in both. Keep positive-score-only selection,
stable document/section-ID tie breaks, at most six sections, and at most 12,000
evidence characters. There is no new score threshold or title-boost coefficient.

The normalization representation, stopword overrides, pipeline resources, title
participation, and synonym policy are part of the versioned retrieval configuration.
Normalization runs outside the worker event loop; inference and resource loading
must not prevent lease renewal. Persistent search caches are not required here.

Execution ruling after the existing load test failed: keep a bounded, process-local
LRU of at most 4096 approved passage representations. Exact title/body bytes key
entries within a normalizer bound to one loaded resource identity. Source hashes
are still checked before every retrieval; changed text is reprocessed. Original and
rewritten queries and conversation history are never cached. This adds bounded
memory usage but no persistent search service or source-verification bypass.

Final-review ruling: source verification and normalization share the database-time
deadline through a bounded blocking-work executor. Coroutine cancellation cannot
terminate a thread; abandoned work remains charged until physical completion.
The worker reduces its claim limit and withdraws its own heartbeat when exhausted.
A permanently blocked thread may require a worker restart. Product protection is
applied across merged query occurrences and before stopword removal; straight and
curly negative contractions retain the canonical negation constraint.

## Synonym fallback

Only an empty primary selection can invoke WordNet. A nonempty but poor primary
selection is a separate ranking problem; this fallback does not solve it.

Proposed initial policy:

- Consider English content words using their spaCy POS and WordNet senses.
- Never expand product names, identifiers, numbers, negation, or constraint terms.
- Retain only candidate lemmas represented in the approved corpus vocabulary.
- Preserve sense grouping. Expand a term only when a single eligible sense
  survives POS and vocabulary filtering; otherwise leave it unexpanded.
- Initially accept single-word candidates only, with at most three distinct
  normalized candidates per query concept and twelve across the query.
- Sort candidates deterministically, exclude originals and duplicates, and run
  one fallback ranking pass with the same section and size bounds.

Corpus filtering is not proof of semantic equivalence. Ambiguous and wrong-sense
cases must be tested, and answer generation still uses the original question.
Do not make additional model calls to select synonyms in this step. NLTK and
spaCy resources are inputs to retrieval, not authoritative banking evidence.

## Models, budgets, persistence, and privacy

Proposed configuration is an optional rewrite_model setting in support TOML;
its effective default is the existing answer-model setting. Preserve the current
answer-model default. Initially use the same provider credentials and endpoint;
independent providers or credentials are outside this increment.

Proposed budgets: one durably reserved rewrite call per knowledge turn, with a
10-second maximum, followed by the existing at-most-two answer attempts. All stages
share the existing database-time 60-second processing deadline. No SDK retries
or hidden repair calls. A successful rewrite consumes one call even when it
returns the original query unchanged or requests clarification.

Store rewriting in a separate turn-owned ledger so it does not consume or weaken
the existing answer-attempt accounting. Reserve before dispatch; journal validated
output before retrieval; reuse successful output after restart. A reserved rewrite
whose result was lost consumes its allowance and terminates with the retry message,
instead of replaying a potentially completed external call.

The rewrite identity binds the original input, bounded history, corpus identity,
effective rewrite model, and prompt/schema version. If configuration changes across
recovery, do not issue a second rewrite or silently switch a completed turn's
rewrite identity; report incompatible state for operator handling.
All writes retain current parent/lease/fence checks.

Add an additive migration; never edit the applied initial SQL migration.
The new table is owned by its turn and removed on turn deletion. Rewritten queries
are conversation content: apply existing expiry/deletion rules, owner isolation,
and protection against late writes. Never export original/re-written queries,
history, resource paths, or raw provider errors into ordinary logs or tracing.

Keep rewrite model, prompt version, elapsed time, usage, status, and failure
category as separately inspectable local metadata. Retrieval diagnostics contain
selected source IDs, retrieval mode, and bounded counts, including abstention
cases; they contain no text bodies. Preserve existing audit/export contracts unless
explicitly extended with sanitized fields.

Current rewrite metadata records the configured model ID and SDK token usage.
Recording a separate provider-resolved snapshot when an operator configures a
moving model alias is deferred; the default model is already a pinned snapshot.

## Resources, versioning, and rollout

Pin spaCy, its compatible English pipeline, NLTK, and required WordNet assets.
Use a reviewed resource manifest with exact package/resource identity and integrity
hashes; install during dependency/setup steps, never while handling a customer
request. Missing or mismatched resources fail readiness with a safe category.
Do not silently substitute a blank spaCy pipeline or another corpus.
Worker startup performs resource verification before claiming work. Public bank
document endpoints validate manifest metadata and source bytes without loading
spaCy or WordNet; NLP resource verification belongs to the RAG path.

Advance retrieval ranking metadata to version 2. Preserve source-document bytes,
section IDs, parser behavior, source roots, approval controls, and all evidence
bounds. Version-1 manifests must remain verifiable using their original hash
rules, so historical artifacts can be inspected and rollback remains defined.
The new RAG runtime requires an explicitly prepared and approved version-2 corpus.

Deployment is an explicit maintenance operation: install/check language resources,
stop owned workers, migrate, prepare/review/approve the version-2 corpus, and start
the new runtime. Neither package installation nor worker startup approves a corpus.
Existing conversations stay bound to their recorded corpus. After activation of
the new corpus, incompatible old conversations must not silently migrate or mix
evidence; users start a new conversation. Preserve old records under retention.
No automatic rollback of database state or corpus approval is permitted.

## Acceptance and delivery boundary

- The original cards question selects relevant card passages and no passages
  solely through "does"; category-complete coverage remains step 2.
- Singular/plural forms, title-only matches, numeric/product constraints,
  negation, and common-word-only input behave as specified.
- Every knowledge turn attempts rewriting; standalone input, follow-ups,
  ambiguous references, topic changes, and insufficient retained context are covered.
- Rewrite timeout, malformed output, and provider errors yield the retry message
  without retrieval or answer calls.
- Synonyms run only on empty primary retrieval, obey all caps, and reject
  ambiguous senses and protected-term expansion.
- Crash recovery reuses completed rewrites; uncertain reservations are not replayed.
  Original answer-attempt, deadline, deletion, expiry, and fencing rules still hold.
- Model and resource configuration, migration upgrades, manifest-version behavior,
  output citations, and tracing privacy have focused automated coverage.
- Existing fixture/control-flow tests remain distinct from live model-quality
  evidence. No paid run, active corpus approval, or production restart is part
  of writing or reviewing this plan.

## Later steps

Step 2 reuses category metadata and handles broad/list questions with adequate
document coverage. Step 3 freezes the broader supported, unsupported, paraphrase,
follow-up, and wrong-sense regression inventory. Step 4 compares retrieval quality,
answer grounding, latency, and model usage with the unchanged version-1 baseline
and completes the agreed live human review before proposing semantic-search work.
