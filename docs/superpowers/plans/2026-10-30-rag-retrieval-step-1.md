# RAG Retrieval Correctness Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. No delegated execution is selected.

**Goal:** Retrieve relevant approved evidence for ordinary English and contextual
banking questions using durable model rewriting, spaCy normalization, and
empty-result-only WordNet fallback.

**Architecture:** Add a turn-owned rewrite ledger and typed rewrite provider before
the existing knowledge retrieval node. Normalize query/title/body terms with a
single spaCy representation; use NLTK/WordNet only after empty primary selection.
Retain authoritative source bytes, bounded evidence, and the answer-attempt ledger.

**Tech Stack:** Python 3.12, spaCy with its compatible English pipeline, NLTK/WordNet,
existing OpenAI structured-output provider, LangGraph, PostgreSQL, Pydantic, uv.

**Spec:** [Draft step 1 design](../specs/2026-10-30-rag-retrieval-step-1-design.md).
This plan is proposed for review; no implementation or corpus approval is authorized
by unchecked tasks.

## Global constraints

- Support English only.
- Rewrite every question entering RAG, including standalone questions.
- A rewrite failure or timeout returns a clear retry message. No original-query fallback.
- Run synonym expansion only if primary normalized retrieval returns no evidence.
- A later answer-model abstention does not automatically trigger another search.
- Give rewriting a separate model setting, initially defaulting to the answer model.
- Keep at most six sections and at most 12,000 evidence characters; retain the
  16,000-character contiguous prior-history bound and 60-second turn deadline.
- Proposed budgets are one rewrite call capped at 10 seconds, followed by at most
  two answer attempts within the remaining deadline. These need design acceptance.
- Documents, history, rewritten queries, and provider output remain untrusted.
- No runtime language-resource downloads, new source roots, automatic corpus
  approval, bank-record reads, embeddings, vector service, or category integration.
- Preserve owner isolation, parent/fence checks, retention, source verification,
  citation membership validation, and deterministic offline operation.
- Run all commands from the repository root. Commit no upstream bodies or secrets.

## Review focus

- Pronouns after a topic change or multiple named cards must not select a guessed
  product; a successful rewrite can ask for clarification (Tasks 3 and 6).
- Negation, comparisons, numbers, and previously unseen product names must survive
  normalization and must not become WordNet expansion targets (Tasks 2 and 6).
- A worker crash after rewrite success must not charge another rewrite, while an
  uncertain reserved call must not be replayed (Tasks 4 and 6).
- Applied migration checksums and old manifest hashes must remain verifiable;
  rollout must not silently rebind old conversations (Tasks 4 and 5).
- Missing NLP assets, source drift, or event-loop starvation must not produce
  partial readiness or prevent lease renewal (Tasks 1, 5, and 6).

## File structure and interfaces

New paths are proposed. Existing interfaces should change only where named below.

| Area | Paths | Responsibility |
|---|---|---|
| Language resources | config/retrieval-resources.json; scripts/setup_retrieval_resources.py; src/veritycx/knowledge/resources.py | Pinned local resources, safe install/check, identity verification |
| Normalization | src/veritycx/knowledge/nlp.py | spaCy initialization and shared searchable token representation |
| Fallback | src/veritycx/knowledge/synonyms.py | POS-aware, corpus-constrained WordNet candidates |
| Selection | src/veritycx/knowledge/retrieval.py | Primary/title matching, conditional fallback, bounded results |
| Rewrite contract | src/veritycx/providers/rewrite.py | Closed request/result models, protocol, live and deterministic adapters |
| Rewrite execution | src/veritycx/providers/rewrite_execution.py | One-call durable dispatch and recovery |
| Rewrite storage | src/veritycx/persistence/rewrites.py; migrations/002_query_rewrites.sql | Fenced reservation/result and per-stage metadata |
| Runtime composition | src/veritycx/orchestration/rag.py | Explicit RAGServices dependency bundle |
| Existing integration | service/configuration.py; orchestration/worker.py; orchestration/graph.py | Settings, dependency construction, stage flow |
| Versions | knowledge/models.py; knowledge/manifest.py; knowledge/configuration.py | Reproducible version-2 corpus preparation and legacy verification |

Define these common interfaces in the owning task:

```
SearchToken(surface: str, lemma: str, pos: str, protected: bool, constraint: bool)
TextNormalizer.analyze(text: str) -> tuple[SearchToken, ...]
TextNormalizer.terms(text: str) -> frozenset[str]
SynonymExpander.expand(tokens: Sequence[SearchToken],
                      *, vocabulary: frozenset[str]) -> tuple[str, ...]
RetrievalSelection(sections: tuple[EvidenceSection, ...],
                   mode: Literal["primary", "synonym", "empty"],
                   expanded_term_count: int)
select_evidence(original_question: str, rewritten_query: str,
                evidence: Sequence[EvidenceSection], *,
                normalizer: TextNormalizer,
                expander: SynonymExpander) -> RetrievalSelection
QueryRewriter.rewrite(request: RewriteRequest) -> RewriteResult  # async
RAGServices(rewriter: QueryRewriter, normalizer: TextNormalizer,
            expander: SynonymExpander)
```

## Task 1: Reproducible language resources and model configuration

**Files:** Modify [pyproject.toml](../../../pyproject.toml), uv.lock,
[support configuration](../../../src/veritycx/service/configuration.py),
[support defaults](../../../config/support.toml), scripts/run_support.py,
service/health.py; create resource files above and
tests/support/unit/test_nlp_resources.py. Extend tests/support/unit/test_configuration.py
and tests/support/contract/test_run_support.py.

**Interfaces:**

```
NLPResourceIdentity(spacy_version: str, pipeline_name: str,
                    pipeline_version: str, nltk_version: str,
                    wordnet_digest: str, policy_version: int)
verify_resources() -> NLPResourceIdentity
Settings.rewrite_model: str | None = None
Settings.effective_rewrite_model -> str
```

The effective rewrite model is rewrite_model when supplied, otherwise model.
Validate nonempty bounded model IDs without hard-coding the answer snapshot into
the new setting. Do not change the existing answer-model default.

- [ ] Write tests named test_rewrite_model_defaults_to_answer_model,
  test_explicit_rewrite_model_is_independent, test_resource_identity_is_verified,
  test_missing_resources_fail_safely, and test_request_path_never_downloads.
  Assert an empty model ID is rejected, exact resource digests are checked,
  unavailable assets return a value-free failure, and networking is never invoked
  by resource verification or request-time initialization.
- [ ] Run the new unit tests and configuration tests; confirm each new case fails
  for the intended missing interface or behavior before implementation.
- [ ] Pin compatible Python-3.12 spaCy/NLTK versions using uv's exact dependency
  workflow. Pin the corresponding English pipeline wheel and WordNet archive in
  the reviewed resource manifest with concrete release URLs and SHA-256 digests.
  Include required POS/lemmatizer lookup assets. Check redistribution licensing.
- [ ] Implement the resource installer/checker with fixed destinations, verified
  bytes, and no request-time downloads. Extend the maintained local setup/launcher
  instructions; worker startup verifies assets before claiming work and existing
  worker-health checks gate chat readiness. Public bank endpoints must not load
  NLP assets merely to validate approved source documents.
- [ ] Run the new tests, locked dependency validation, and launcher contracts.
  Expect pass, with no live provider calls. Keep resource identity metadata
  separate from secret environment values.
- [ ] Commit this task when implementation is authorized, using the repository's
  existing commit style.

## Task 2: Shared normalization, primary ranking, and WordNet fallback

**Files:** Create knowledge/nlp.py and knowledge/synonyms.py; modify
[retrieval.py](../../../src/veritycx/knowledge/retrieval.py);
extend tests/support/unit/test_retrieval.py and add test_nlp.py and test_synonyms.py.
Use the approved synthetic documents without changing their bodies.

**Consumes:** Task 1 resource identity. **Produces:** SearchToken, TextNormalizer,
SynonymExpander, RetrievalSelection, and select_evidence interfaces above.
Retain the original version-1 retrieve function for frozen baseline comparisons;
the new runtime will call select_evidence explicitly.

- [ ] Add test_cards_question_ignores_does_and_matches_card: select against the
  authored corpus and assert Cedar/Hazel passages are found and no conflict
  document is selected only through auxiliary words. Do not require all three
  card-category documents in this step.
- [ ] Add test_title_only_match, test_plural_forms_match,
  test_common_words_or_constraints_alone_select_nothing,
  test_product_names_and_numbers_preserved, test_negation_preserved,
  and test_retrieval_bounds_and_ties. Assert duplicate query concepts do not
  inflate scores, six-section/12,000-character bounds hold, and text/IDs are unchanged.
- [ ] Add a counting fake expander: test_synonyms_only_after_empty_primary must
  assert zero calls for nonempty primary selection and exactly one for empty
  selection. Test ambiguous senses, proper names, numeric terms, duplicate
  candidates, multiword exclusions, three-per-concept and twelve-total caps.
- [ ] Run these focused tests and confirm the intended failures.
- [ ] Implement the shared spaCy representation and ranking described in the
  design. Batch normalization, preserve constraints without allowing them to
  produce constraint-only relevance, and include title/heading terms once.
- [ ] Implement the WordNet adapter behind the expander protocol. Filter by POS,
  corpus vocabulary and unique surviving sense; apply deterministic caps and
  the same rank/budget policy to the single fallback pass. Do not call a model.
- [ ] Run focused tests using fake WordNet candidates for policy edge cases and
  at least one actual local-resource normalization/WordNet smoke check.
  Expect pass without network. Document that no-evidence fallback does not
  repair a nonempty irrelevant result.
- [ ] Commit the tested normalization and selection change.

## Task 3: Typed query rewriting and live/offline adapters

**Files:** Create providers/rewrite.py, tests/support/unit/test_query_rewrite.py,
and tests/support/contract/test_query_rewrite_provider.py; modify
providers/protocol.py only to add an optional distinct rewritten_query field to
ProviderRequest. Update the provider contract and provider README.

**Produces:**

```
RewriteRequest(question: str, context: tuple[ContextMessage, ...],
               correlation_id: str, corpus_version: str,
               remaining_seconds: float, prompt_version: Literal[1] = 1)
SearchRewrite(disposition: Literal["search"], query: str)
ClarifyRewrite(disposition: Literal["clarify"], text: str)
RewriteResult(result: SearchRewrite | ClarifyRewrite,
              model: str, usage: Usage | None)
OpenAIQueryRewriter(client: AsyncOpenAI, model: str)
DeterministicQueryRewriter()
```

Require question/query lengths 1-8,000, history at most 16,000 characters,
clarification 1-800, and remaining_seconds greater than zero and at most 60.
Use a root object wrapping the discriminated union for structured output.
The deterministic adapter is an explicitly selected offline substitute with
authored identity/follow-up/clarify cases, never a live failure fallback.

- [ ] Write schema tests for missing/extra fields, malformed JSON, unsupported
  dispositions, empty/oversized query, and oversized history.
- [ ] Write real-SDK mock-transport tests using the pinned SDK's transport type:
  assert configured rewrite model, structured schema, tools=[], store=false,
  max_retries=0, max_output_tokens=2048, and a timeout capped at 10 seconds.
  Assert successful query, clarification, malformed output, timeout, and sanitized
  API failure results. No raw provider body may appear in errors.
- [ ] Run the tests to establish failures, then implement the contract/adapters.
  Supply original message and role-separated history; instruct preservation of
  subject, numbers, negation and constraints, with clarification on ambiguity.
  Populate model/usage from the SDK, never model-authored metadata.
- [ ] Add authored tests for Cedar -> its replacement fee, two-card ambiguity,
  topic changes, standalone queries, untrusted history instructions, and a
  reference whose antecedent is outside retained history. Treat deterministic
  cases as control-flow evidence, not proof of live rewriting quality.
- [ ] Run the provider contracts and existing selected-citation tests; expect pass.
  Existing ProviderRequest callers remain valid through the optional field.
- [ ] Commit the typed rewriting boundary.

## Task 4: Additive migration and durable one-call rewrite ledger

**Files:** Create persistence/migrations/002_query_rewrites.sql,
persistence/rewrites.py, providers/rewrite_execution.py, and
tests/support/integration/test_rewrite_recovery.py. Modify persistence/migrate.py,
persistence/models.py, migration/maintenance READMEs, and migration/retention tests.

**Produces:**

```
RewriteRow(turn_id, request_digest, model, prompt_version, status,
           result_json, failure_category, input_tokens, output_tokens,
           started_at, ended_at, selected_source_ids,
           retrieval_mode, expanded_term_count)
RewriteLedger.lookup(job: WorkJob, digest: str) -> RewriteRow | None  # async
RewriteLedger.reserve(job: WorkJob, digest: str, model: str,
                      prompt_version: int) -> Reservation  # async
RewriteLedger.save(job: WorkJob, result: RewriteResult | None,
                   failure: str | None = None) -> None  # async
RewriteLedger.record_retrieval(job: WorkJob,
                              selection: RetrievalSelection) -> None  # async
invoke_rewriter(rewriter: QueryRewriter, ledger: RewriteLedger,
                job: WorkJob, request: RewriteRequest,
                model: str) -> RewriteResult  # async
```

Use support_app.query_rewrites: one rewrite row per turn, foreign key to turns
with ON DELETE CASCADE. Include selected_source_ids (empty JSON array by default),
retrieval_mode (null until selection), and expanded_term_count (zero by default)
in migration 002 from the start; constrain them to the selection bounds.
Record reservation before dispatch; only the current worker fence can save.
Reuse matching successful rows. A mismatched identity is incompatible_state;
a reserved row without output is spent and yields a retry outcome.
The existing answer attempts table and its ordinal limit remain unchanged.

- [ ] Add native database tests for fresh install, version-1 upgrade, repeated
  migration, partial/unknown history rejection, checksum mismatch, and runtime-role
  privilege separation. Assert initial migration bytes/checksum are unchanged.
- [ ] Add tests for reserve-before-dispatch, one-call enforcement, success reuse,
  crash after success, crash before result persistence, changed model/digest,
  stale fence, and deadline expiration. Assert rewrite attempts never alter the
  count or outputs in support_app.attempts.
- [ ] Run these cases against the dedicated test database to establish failures.
- [ ] Extend the administrative migration runner to validate/apply a checksummed
  ordered migration prefix. Runtime schema checks require the complete current
  ledger. Preserve the independent Chatwoot migration checks and grants.
- [ ] Implement ledger/invocation behavior with one call capped by both 10 seconds
  and remaining database time. Use existing parent-before-job locks and sanitized
  failure handling. Persist structured results and observed usage.
- [ ] Prove expired/deleted turns remove rewrite content and a late worker cannot
  recreate it; test ON DELETE CASCADE through the actual retention workflow.
- [ ] Run migration, recovery, attempt, retention, and Chatwoot integration tests;
  expect pass without paid calls. Commit the storage/execution change.

## Task 5: Retrieval-version metadata and explicit corpus transition

**Files:** Modify knowledge/models.py, knowledge/manifest.py,
knowledge/configuration.py, scripts/manage_support.py, tests/support/unit/test_corpus.py,
and management contracts. Update the knowledge provider contract and knowledge README.

**Interfaces:**

```
build_manifest(root: Path, mode: Literal["synthetic", "official"], pin: str,
               *, ranking_version: Literal[1, 2] = 2,
               resource_identity: NLPResourceIdentity | None = None)
    -> CorpusManifest
```

Preserve version-1 canonical hash rules exactly when verifying historical manifests.
Version 2 binds resource identity and normalization/synonym policy versions.
Preparation defaults to version 2; approval remains an explicit existing hash action.

- [ ] Freeze a version-1 fixture hash, then add tests proving old verification is
  byte-identical. Test version-2 reproducibility, changed resource/policy identity,
  source drift, and resource/model mismatch.
- [ ] Add tests asserting prepare never activates, startup never approves, and a
  v2 runtime rejects a v1 active corpus with a safe category. Verify old
  conversations cannot silently adopt the new corpus.
- [ ] Run to confirm failures, then implement the new manifest variant and
  version-dispatched validation. Do not edit documents, parser output, section IDs,
  source permissions, or retained history to make migration pass.
- [ ] Run corpus/management/source-isolation tests; expect pass. Record an explicit
  maintenance rollout and new-conversation requirement in current documentation.
- [ ] Commit versioning and rollout support. Do not approve the user's active
  corpus while performing the implementation task.

## Task 6: Compose the complete RAG stage with existing workers

**Files:** Create orchestration/rag.py; modify orchestration/worker.py,
orchestration/graph.py, orchestration/state.py, providers/openai.py,
observability/audit.py, and service/health.py as required.
Update every process_job call in service/validation.py and support tests to pass
explicit RAGServices. Add tests/support/integration/test_rag_retrieval_pipeline.py.

**Consumes:** Tasks 1-5. **Produces:** Required keyword-only rag: RAGServices on
process_job and execute_job. Worker construction selects live or deterministic
rewriting explicitly alongside its existing answer provider.

- [ ] Write stage-spy tests proving every knowledge turn rewrites, including a
  standalone question; human/operation routing still acts on original input.
  Original message and rewritten query remain distinct in the answer request.
- [ ] Assert a rewrite error publishes exactly
  "We couldn't prepare your question for search. Please try again."
  with no retrieval/answer calls; clarification also stops retrieval.
  Assert empty primary -> one synonym pass -> ordinary abstention when empty,
  and answer-model abstention never triggers another search.
- [ ] Test history ownership/order/bounds, contradictory assistant text that is
  not policy evidence, ambiguous products, timeout within the shared 60 seconds,
  deletion during rewriting, worker lease renewal during NLP inference, and
  recovery after journal persistence but before graph checkpoint progress.
- [ ] Run these tests to establish failures. Implement explicit stage composition,
  use the configured rewrite model, and run synchronous NLP off the event loop.
  Avoid unnecessary query bodies in checkpoint state; recover from the ledger.
- [ ] Keep per-stage model/usage/failure metadata in the rewrite row. Call the
  fenced record_retrieval interface to populate its existing selected-ID, mode,
  and expansion-count fields, including abstention outcomes. Do not edit the
  migration applied in Task 4.
- [ ] Verify ordinary logs and optional exports contain no original question,
  rewritten query, history, source bodies, or raw provider errors. Retain answer
  citation validation and existing audit fields without falsely combining model usage.
- [ ] Run the full offline support suite, including updated explicit offline
  dependency fixtures, restart cases and native Chatwoot handoff. Expect pass;
  do not substitute a fixture rewriter when live execution fails.
- [ ] Commit the integrated step-1 RAG flow.

## Task 7: Documentation, checks, and step-by-step handoff

**Files:** Update root README, scripts/README, config/README, touched module/test
READMEs, docs/README, the current knowledge provider contract, and these planning
documents. Preserve historical evidence statements and unrelated open tasks.

- [ ] Document installation/check commands, independent rewrite_model configuration,
  exact failure/clarify/abstain behavior, per-stage budgets, privacy, and version-2
  prepare/review/approval steps. Explain the existing-v1-conversation limitation.

- [ ] Run the following existing checks and fix only relevant failures:

  ```
  uv lock --check
  uv run python scripts/check_environment_contract.py
  uv run ruff format --check src scripts tests
  uv run ruff check src scripts tests
  uv run mypy --strict src scripts tests
  uv run pytest tests -m "not live"
  uv run mdformat --check docs/superpowers/specs/2026-10-30-rag-retrieval-step-1-design.md docs/superpowers/plans/2026-10-30-rag-retrieval-step-1.md
  ```

  Full pytest requires the maintained dedicated native test database and installed
  local NLP resources. Missing prerequisites must be reported, not silently skipped.

- [ ] Report exact focused/full test results and demonstrate the original cards
  query's selected source IDs with the offline retriever. Separately report which
  follow-up tests use a deterministic rewriter or mocked transport.

- [ ] If explicitly authorized for live validation, use a new owned conversation
  after the reviewed corpus transition; verify standalone and contextual questions,
  retry behavior via controlled offline failures, and cited policy answers. Record
  metadata and human review honestly; do not claim a full live grounding acceptance.

- [ ] Finish this step before beginning category integration. Carry the untouched
  version-1 baseline and identified cases into steps 3-4. Commit documentation when
  execution is authorized and report material limitations.

## Later plans

- Step 2: shared category selection and broad-question coverage, including Pine.
- Step 3: larger retrieval-quality corpus with independent supported/unsupported,
  paraphrase, wrong-sense and conversational cases.
- Step 4: before/after recall and irrelevant-hit measures, category coverage,
  unsupported-answer behavior, latency, token usage and human-reviewed grounding.
  Choose thresholds after freezing cases and observing the baseline; do not
  introduce embeddings or a separate reranker merely because they are absent.

## Plan review

The user's decisions are separated from proposed budgets, limits, resource packaging,
and migration details in the design. Native implementation in the current session
is recommended because normalization, ledger, corpus metadata and graph contracts
are tightly connected. Review this design and plan before implementing task 1;
implementation is not part of this planning deliverable.
