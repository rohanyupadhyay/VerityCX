# RAG Category Retrieval Step 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Preserve native execution in this session; no delegated implementation is selected.

**Goal:** Answer category overviews from documented products with cited, bounded
coverage, including Cedar, Hazel, and Pine for the original cards question.

**Architecture:** Bind the bank-page category classifier and original document
titles into a version-3 approved corpus snapshot. Extend the existing durable
rewrite call with typed search scope, dispatch focused or category selection, and
publish grounded overviews with an application-rendered scope note.

**Tech Stack:** Existing Python 3.12, spaCy, NLTK/WordNet, OpenAI structured output,
LangGraph, PostgreSQL 18.6, Pydantic, uv, and the maintained offline/native harness.
No new dependency is proposed.

**Spec:** [Approved step-2 design](../specs/2026-11-02-rag-category-retrieval-step-2-design.md).
The user approved the design on 2026-11-02. The user approved this plan for native implementation on 2026-11-02. The existing feature branch is feat/rag-category-retrieval-step-2.

## Global constraints

- English only; reuse the existing six service categories, including Other policies.
- One rewrite call, capped at ten seconds; at most two answer attempts; one shared
  database-time sixty-second deadline. No extra classification call or SDK retries.
- At most six evidence sections, 2000 characters per section, 12,000 evidence
  characters, 16,000 history characters, and 8000 final answer characters.
- Preserve source bytes, parser/section IDs, source roots, owner isolation,
  fencing, retention, citation validation, corpus approval, bounded inference
  capacity, and the passage-only cache.
- Keep v1/v2 hash verification and lexical baselines. Advance chat to approved
  corpus v3, rewrite prompt 2, and answer prompt 3 explicitly.
- Category metadata and history are discovery context, never policy evidence.
  Preserve the original question and its qualifiers throughout the flow.
- Focused selection retains step-1 matching and empty-result-only WordNet fallback.
- No embeddings, reranker, private word dictionary, new UI, product catalogue,
  bank-record reads, or broader step-3/4 benchmark in this increment.
- Keep app database/corpus/runtime unchanged while implementing. Use only the
  dedicated test database and fixed test cache for native verification.
- App migration, corpus activation, paid calls, push, and merge require separately
  authorized execution; design/plan approval alone does not authorize them.
- Run commands from the repository root. Do not print or commit credentials,
  upstream document bodies, or private generated data.

## Review focus

- A category-looking first heading must not reclassify a full document: Task 1
  test_heading_does_not_change_catalog_assignment.
- An unavailable category or unsupported product qualifier must not redirect the
  answer into an easier category: Tasks 2/5 empty-category and qualifier tests.
- A related-title group larger than the remaining budget must be deferred intact,
  including at a multi-category boundary: Task 3 conflict and budget tests.
- A valid answer near 8000 characters must leave room for the fixed scope note,
  including separators: Task 4 exact-boundary tests.
- Re-exporting an old audit row must not label it with the new prompt version:
  Task 5 historical-audit provenance and recovery tests.

## Files and dependency order

| Task | Owning paths | Result |
|---|---|---|
| 1 | knowledge/catalog.py, models.py, manifest.py, configuration.py; new knowledge/scope.py | Shared typed category policy, scope contracts, approved v3 snapshot |
| 2 | providers/rewrite.py, rewrite_execution.py; rewrite unit/transport tests | One-call version-2 typed rewriting |
| 3 | new knowledge/category_retrieval.py; knowledge/retrieval.py | Bounded overview selection and coverage |
| 4 | providers/protocol.py, openai.py; policy/outputs.py | Grounded overview requests and final scope note |
| 5 | migration 003; persistence/rewrites.py, models.py, migrate.py; orchestration/graph.py; observability/audit.py, export.py | Fenced storage, honest metadata, complete graph |
| 6 | READMEs, provider contract, validation metadata, design/plan execution record | Maintained commands, checks, and explicit activation handoff |

Tasks 2–4 consume Task 1 contracts. Task 5 integrates Tasks 1–4; Task 6 verifies
the complete feature. Treat the closely connected interfaces as one native plan.

## Task 1: Shared category policy and version-3 source snapshot

**Files:** Modify [catalog.py](../../../src/veritycx/knowledge/catalog.py),
[models.py](../../../src/veritycx/knowledge/models.py),
[manifest.py](../../../src/veritycx/knowledge/manifest.py),
[configuration.py](../../../src/veritycx/knowledge/configuration.py);
create src/veritycx/knowledge/scope.py and tests/support/unit/test_category_catalog.py;
extend tests/support/unit/test_retrieval_versions.py,
tests/support/unit/test_corpus.py and tests/support/contract/test_bank_information.py.

**Interfaces produced:**

- catalog.CategoryKey: the existing accounts, savings, cards, payments, deposits,
  and other literal keys; retain CATEGORIES as the single ordered label mapping.
- catalog.CategoryPolicyIdentity(policy_version: Literal[1], digest: str), with a
  lowercase 64-hex SHA-256 digest, and
  category_policy_identity() -> CategoryPolicyIdentity.
- models.CatalogEntry(document_id: str, title: str, category: CategoryKey).
- CorpusManifest.ranking_version accepts 1, 2, 3; catalog_index:
  tuple[CatalogEntry, ...] | None; category_policy: CategoryPolicyIdentity | None.
  V3 requires both, exactly matching the document inventory; legacy versions
  require neither. Existing retrieval_resources rules remain.
- scope.SearchScope(scope: Literal[focused, category_overview],
  categories: tuple[CategoryKey, ...]); both fields required, distinct keys, at
  most six, canonical CATEGORIES order, empty iff focused.
- scope.CategoryHint(key: CategoryKey, label: str), and
  category_hints(catalog_index: Sequence[CatalogEntry]) -> tuple\[CategoryHint, ...\]:
  emit canonical labels for nonempty categories.
- scope.CategoryCoverage(eligible_document_count: int,
  represented_document_count: int, coverage_truncated: bool): counts nonnegative,
  represented \<= eligible, truncated iff represented < eligible.
- scope.SearchContext(search_scope: SearchScope,
  coverage: CategoryCoverage | None): coverage required for overview and absent
  for focused. Keep search metadata independent of provider authority.

Avoid runtime import cycles: catalog may use postponed annotations and a
TYPE_CHECKING import for KnowledgeDocument; it must not import models at runtime
just to annotate category_for. Preserve its current classification behavior.

- [x] Write the schema/category/hash tests before implementing. Pin:

  ```python
  def test_legacy_hashes_remain_frozen():
      root, _, pin = source_mode("synthetic")
      assert build_manifest(root, "synthetic", pin, ranking_version=1).aggregate_hash == (
          "d93ccecdefc8d84cf264619ef4ebd8ada144db9e0f975d4cc810c33aa8069460"
      )
      assert build_manifest(root, "synthetic", pin, ranking_version=2).aggregate_hash == (
          "92126bf8d93182482cce66c599890de1db2f66e509dab2bb39a720e6056933b1"
      )
  ```

  Add test_catalog_matches_bank_categories: v3 card IDs equal policy-03,
  policy-08, policy-16 and agree with category_for on full source documents.
  test_heading_does_not_change_catalog_assignment uses an original title in Other
  policies and a first heading containing card; both interfaces retain Other.
  Reject duplicate/foreign/missing catalog IDs, unknown categories, malformed
  coverage, and incorrect scope combinations. Empty known categories remain valid.

- [x] Run uv run pytest tests/support/unit/test_category_catalog.py
  tests/support/unit/test_retrieval_versions.py -q; confirm the new interfaces and
  explicit v2 fixture expectations fail before implementation.

- [x] Implement the interfaces and default new preparation to ranking 3. Hash
  category data in priority order, including CATEGORIES order, title-rule order,
  synthetic assignments, and the case-folded-original-title grouping policy.
  Build the index from full parsed documents, never passage headings.
  Include catalog/policy metadata only in v3 canonical hash payloads; retain
  exact legacy payloads. Reconstruct v3 index from verified source bytes.
  Make active_corpus require v3 and matching current category/NLP identities.
  Public active_documents continues verifying v1/v2 sources without loading NLP.

- [x] Run the focused tests plus test_corpus.py, test_review_regressions.py, and
  test_bank_information.py. Expect pass and unchanged policy bodies. Assert
  category-policy or mapping drift requires reapproval and prepare never activates.
  Update existing default-preparation assertions without weakening frozen baselines.

- [x] Commit the tested snapshot/scope contract using the established docs/feat/fix style.

## Task 2: Typed overview intent in the existing rewrite call

**Files:** Modify [rewrite.py](../../../src/veritycx/providers/rewrite.py),
[rewrite_execution.py](../../../src/veritycx/providers/rewrite_execution.py);
extend tests/support/unit/test_query_rewrite.py and
tests/support/contract/test_query_rewrite_provider.py.

**Consumes:** SearchScope, CategoryHint, category_hints from Task 1.
**Produces:** SearchRewrite inherits SearchScope and retains disposition=search
and nonblank query; search_scope() -> SearchScope returns just its scope fields.
RewriteRequest adds available_categories: tuple[CategoryHint, ...] bounded at six
and prompt_version: Literal[2] = 2. ClarifyRewrite and QueryRewriter signatures stay.

- [ ] Add tests with concrete schema assertions:

  ```python
  result = SearchRewrite(
      disposition="search", query="cards documented by VerityCX",
      scope="category_overview", categories=("cards",),
  )
  assert result.search_scope() == SearchScope(
      scope="category_overview", categories=("cards",)
  )
  ```

  Reject omitted scope/categories, empty overview categories, nonempty focused
  categories, duplicate/unknown keys, extra fields, and more than six hints.
  Assert canonical category order and unchanged question/history bounds.
  Test malformed provider output and clear sanitized failure categories.

- [ ] Run both rewrite test modules and observe intended RED failures.

- [ ] Extend the single structured request and instructions to distinguish
  overviews from focused lookups, retain qualifiers, honor topic changes, and
  clarify missing/ambiguous antecedents. Include server-derived hints without
  authorizing unsupported facts. Keep tools=[], store=false, retries=0,
  max_output_tokens=2048, and the ten-second cap. Ensure digest includes version
  and available-category metadata. Never upgrade old result JSON silently.
  Update explicit test fakes to construct focused scope rather than relying on
  default missing fields. Add authored offline cards and multi-category overview
  cases; retain the authored Cedar follow-up and ordinary focused fixture behavior.

- [ ] Run real-SDK mocked transport tests for focused, overview, clarification,
  invalid schema, timeout, and API failure. Assert exactly one request and
  scope/qualifier instructions. Include business-card eligibility and a Martian
  product question as control-flow cases; do not label mocked output live fidelity.

- [ ] Commit the tested rewrite boundary. Native persistence prompt-version
  changes and full graph tests are completed together in Task 5.

## Task 3: Coverage-first bounded category selection

**Files:** Create src/veritycx/knowledge/category_retrieval.py and
tests/support/unit/test_category_retrieval.py; extend
[retrieval.py](../../../src/veritycx/knowledge/retrieval.py) only as below.

**Consumes:** Task 1 CatalogEntry, SearchScope, SearchContext, CategoryCoverage;
existing TextNormalizer, SynonymExpander, and v2 select_evidence.
**Produces:**

```text
select_scoped_evidence(original_question: str, rewritten_query: str,
    evidence: Sequence[EvidenceSection], *,
    search_scope: SearchScope, catalog_index: Sequence[CatalogEntry],
    normalizer: TextNormalizer, expander: SynonymExpander) -> RetrievalSelection
RetrievalSelection.context: SearchContext | None = None
RetrievalSelection.mode: primary | synonym | category | empty
```

Leave v1 retrieve and the v2 select_evidence algorithm unchanged. The wrapper adds
focused context to v2 results without changing selected IDs, order, or expansion.

- [ ] Add test_original_cards_overview_covers_pine using the unchanged synthetic
  source snapshot, real normalizer, and scope category_overview/cards. Assert:

  ```python
  assert {s.document_id for s in selection.sections} == {
      "policy-03", "policy-08", "policy-16"
  }
  assert selection.mode == "category"
  assert selection.expanded_term_count == 0
  assert selection.context.coverage.eligible_document_count == 3
  assert selection.context.coverage.represented_document_count == 3
  assert selection.context.coverage.coverage_truncated is False
  ```

  Add focused_equals_v2 assertions for IDs/order/synonym call count; zero-score Pine
  inclusion; empty category => empty/zero answer candidates; cross-category fair
  allocation; stable ties; six sections and 12,000 characters; large multi-section
  documents; unchanged source text/IDs; coverage counts document IDs, not sections.
  Add test_related_versions_are_indivisible_at_budget_boundary and
  test_oversized_related_group_is_deferred: no selected group has only one of its
  related documents when all are eligible. A group larger than the entire budget
  produces no partial group and honest truncated coverage.

- [ ] Run uv run pytest tests/support/unit/test_category_retrieval.py -q and
  confirm the missing selector/metadata fails before implementation.

- [ ] Implement selection under the existing evidence budgets: group by the
  approved original title's casefold, rank by maximum v2 normalized section score
  using the eligible subcorpus's term frequencies, then stable document/section
  IDs. Select one best section per document for a complete fitting group.
  Round-robin categories in canonical order; examine each group's position once,
  deferring a non-fitting group intact. Only after the coverage pass, fill spare
  slots with the best remaining sections of represented documents. Do not let
  duplicate sections displace any unrepresented group that would fit.
  Group eligible documents globally, allocating a group spanning requested
  categories to the earliest canonical category represented by its members.
  Select it only once; do not authorize documents outside the requested categories.
  Validate section document membership against the approved index; do not read
  paths or create synthetic evidence. Empty overview selection remains scoped and
  never falls through to global lexical or WordNet search.

- [ ] Run the new cases with existing test_nlp.py, test_synonyms.py, and
  test_retrieval.py. Expect unchanged baselines, all budgets respected, and no
  resource download or new query/history cache.

- [ ] Commit the tested selector and bounded coverage contract.

## Task 4: Grounded overview answers and publication limits

**Files:** Modify [protocol.py](../../../src/veritycx/providers/protocol.py),
[openai.py](../../../src/veritycx/providers/openai.py),
[outputs.py](../../../src/veritycx/policy/outputs.py);
extend tests/support/contract/test_providers.py,
tests/support/unit/test_models.py and test_safety.py; create
tests/support/unit/test_category_answers.py.

**Consumes:** Task 1 SearchContext and Task 3 selected sections.
**Produces:** ProviderRequest.search_context: SearchContext | None = None;
prompt_version: Literal[3] = 3; read-only answer_text_limit -> int. The overview
scope-note constant lives in knowledge/scope.py so provider/policy imports do not
form a cycle:

“These products or services are documented in the approved policies; this may not
be a complete list of offerings.”

answer_text_limit is 8000 for other scopes, or 8000 minus len(note) minus one
newline for overview answers. Count the joined claim text including its separators.

- [ ] Test that a valid overview answer gets exactly one note, preserves its
  citations, and is at most 8000 characters. At the exact joined-text limit it
  succeeds; one character over fails with invalid_output. Test multiple claims
  and newline accounting. Focused answers and non-answer dispositions get no note.
  Foreign or fabricated source IDs still fail.

  ```python
  def test_overview_request_reserves_scope_note():
      request = ProviderRequest(
          correlation_id="fixture", question="Which cards are documented?",
          remaining_seconds=60.0,
          search_context=SearchContext(
              search_scope=SearchScope(scope="category_overview", categories=("cards",)),
              coverage=CategoryCoverage(
                  eligible_document_count=3, represented_document_count=3,
                  coverage_truncated=False,
              ),
          ),
      )
      assert request.answer_text_limit == 8000 - len(OVERVIEW_SCOPE_NOTE) - 1
  ```

- [ ] Run uv run pytest tests/support/unit/test_category_answers.py
  tests/support/contract/test_providers.py -q and observe new failures.

- [ ] Add the scope/coverage metadata and prompt-v3 instructions while retaining
  the original question as authoritative. Authorize documented-product lists
  without demanding an exhaustive catalogue, require every factual claim to cite
  selected passages, and forbid cross-product facts or erasing qualifiers.
  State the application-derived answer_text_limit in the trusted instructions.
  validate_result first validates citation membership and actual joined-text
  length, then appends the fixed note only to an overview answer. Never truncate
  factual claims to make room. Existing invoke_provider validation/retry accounting
  must cover note/length failures; do not add a repair call.

- [ ] Run provider/model/safety tests, including wrong-category and unsupported-
  qualifier requests. Mock tests assert contracts/instructions and publication
  gates; actual semantic behavior needs the later opt-in live checks.

- [ ] Commit the tested request/publication change. Per-event prompt provenance,
  graph wiring, and legacy export handling belong to Task 5.

## Task 5: Additive storage, durable diagnostics, and complete graph

**Files:** Create src/veritycx/persistence/migrations/003_category_retrieval.sql;
modify persistence/migrate.py, rewrites.py, models.py;
orchestration/graph.py; observability/audit.py and export.py;
tests/support/conftest.py and affected explicit fakes;
extend integration/test_migrations.py, test_rewrite_recovery.py,
test_rag_retrieval_pipeline.py, test_retention.py;
add tests/support/integration/test_category_rag.py and extend
tests/support/unit/test_trace_privacy.py.
Create tests/support/migration_harness.py for genuinely isolated upgrade/fresh-
install cases; never reset the shared dedicated database to an older schema.

**Consumes:** Tasks 1–4. **Produces:** RewriteRow.prompt_version accepts 1|2;
retrieval_mode accepts category. New nullable columns/fields are search_scope,
category_keys, eligible_document_count, represented_document_count, and
coverage_truncated. Old rows retain null scope/coverage as unknown. New focused
rows use focused and [] categories with null coverage; overviews use nonempty
categories and measured coverage, including zero-result searches.

As an implementation ruling for truthful version-3 exports, add nullable
support_app.audit.prompt_version and AuditEventRow.prompt_version accepting 1|2|3.
The keyword-only prompt_version argument on commit_result and commit_result_on
has type Literal[1, 2, 3] | None, defaults to None, and is written only on a newly committed result. Current answer
requests pass 3; non-model outcomes and unverifiable historical rows stay unknown.
metadata(event, provider) derives knowledge-vN from the stored event, or unknown.
Do not relabel an old completed result merely because a new worker exports it.

- [ ] Add native tests for upgrading a v2-prefix schema, fresh install, repeated
  migration, immutable 001/002 checksums, unknown/partial migration history,
  runtime DDL denial, retained prompt-1 rewrite rows and null historical metadata.
  Use only dedicated test storage and transactional/isolated schema fixtures.
  Add category diagnostics shape/cap/enum tests, stale-fence rejection, restart
  success reuse, spent uncertain reservation, changed scope/hints digest rejection,
  deletion cascade, and a live one-second shared-deadline fixture.
  The new migration harness exposes owned_migration_database(root: Path,
  processes: OwnedProcesses) -> context manager[MigrationTestDatabase], with
  redacted admin/runtime DSNs. Use the installed native 18.6 binaries under the
  existing CI PG_PREFIX or the maintained local prefix, a new temporary data
  directory, private generated test credentials, and a free loopback port.
  Run the foreground postgres process through OwnedProcesses and stop only its
  retained handle. Create only its fresh veritycx_support_test database and role.
  Validate both DSNs with require_test_database. To reproduce the v2 prefix, run
  migrate on this private cluster with inventory temporarily limited to immutable
  001/002, then restore the full inventory and migrate to 003. Assert final
  migration versions equal [1, 2, 3] and preexisting fixture rows survive.
  Missing binaries are a reported prerequisite failure, not a skipped test.
- [ ] Run these focused cases before implementing and record intended failures.
  A schema mismatch before migration is expected, not permission to edit 001/002.
- [ ] Implement migration 003 and ordered inventory extension. Replace the named
  rewrite prompt/mode constraints additively; accept retained prompt 1 and new 2.
  Bound category_keys to an array of at most six known keys, require consistent
  scope/coverage shapes and represented \<= eligible, and preserve selected-ID caps.
  record_retrieval(job, selection) writes diagnostics in its existing fenced
  transaction. Add truthful per-event answer prompt metadata as specified above.
- [ ] Wire the graph: require v3 snapshot; compute hints from its catalog index;
  invoke the version-2 rewriter exactly once; clarify/error short-circuit; run
  select_scoped_evidence in rag.inference; record diagnostics even for empty
  searches; pass SearchContext to the answer request; commit with its prompt version.
  Legacy corpus mismatch must fail before a new rewrite. Keep human/operation
  routing on the original input and preserve all existing lease/deadline guards.
- [ ] Run native graph tests with a recording rewrite and answer provider:
  cards overview gets exactly IDs 03/08/16, three corresponding citations and the
  note; Cedar fee uses focused selection; no extra rewrite/answer attempts;
  empty category abstains without answer; answer abstention does not search again;
  a nonempty category for which no complete related group fits returns
  clarification asking for a narrower policy/category question, with zero answer
  attempts and honest truncated coverage;
  unknown product or business qualifier remains in the answer request even if the
  fake classifier chooses cards; topic change and missing context remain isolated.
  Test actual API owner isolation, migration recovery, legacy-conversation
  rejection, foreground lease renewal during selection, and retention.
  Test exporting an old null-version audit row yields unknown and no question,
  history, source body, private path, or raw error; new answers export knowledge-v3.
- [ ] Commit the integrated storage/graph change after focused native tests pass.

## Task 6: Documentation, full checks, and implementation handoff

**Files:** Update README.md, config/README.md, scripts/README.md, docs/README.md;
touched knowledge/provider/policy/persistence/orchestration/observability/test
READMEs; specs/002-durable-knowledge-support/contracts/knowledge-provider.md;
service/validation.py prompt metadata; this plan and the approved design's
execution record. Preserve dated prior evidence and unrelated open work.

- [ ] Document the new intent/selection behavior, honest list scope, related-title
  grouping, oversized/empty-category behavior, unchanged budgets, local diagnostics,
  prompt versions, v3 preparation/approval, migration 003 and new-conversation
  requirement. Update current validation result metadata to answer prompt 3,
  distinguishing current validation runs from old audit events.

- [ ] Run the maintained checks and fix relevant failures:

  ```text
  uv lock --check
  uv run python scripts/setup_retrieval_resources.py --check
  uv run python scripts/check_environment_contract.py
  uv run ruff format --check src scripts tests
  uv run ruff check src scripts tests
  uv run mypy --strict src scripts tests
  uv run mdformat --check src scripts tests config docs
  uv run yamlfix --check .github/workflows/quality.yml .github/workflows/support-integration.yml
  uv run pytest tests -m "not live" -q
  ```

  Native tests require maintained dedicated runtime/admin test DSNs. Do not print
  their values. If schema setup is needed, use the maintained
  uv run python scripts/setup_support_local.py without --app to update only test
  storage. Run the standalone validator too: uv run python
  scripts/validate_support.py --suite offline. Keep its parent-side metadata
  explicitly in the fixed test namespace, with no application corpus dependency.

- [ ] Record exact results and any latency failures before retries. The existing
  30-turn deterministic load target stays p95 \<= 5 seconds with zero leaks and
  a one-second scan cadence. Do not relax the target or delete unrelated test rows.
  Run frontend checks only if frontend/product contracts change; no UI change is
  planned. CI retains its cross-platform resource setup and native test gates.

- [ ] Demonstrate the original question's three selected document IDs and the
  final scoped answer with deterministic/transport fixtures. Clearly label this
  as control-flow evidence. Prepare a v3 manifest and compare source inventories
  without approving or migrating the app.

- [ ] If separately authorized, run a bounded live smoke against owned test
  storage with the already selected credential: original cards, Cedar fee,
  contextual follow-up, absent antecedent, unsupported product and unsupported
  qualifier. Check each listed product and citation manually; structured output
  alone cannot prove semantic fidelity. Keep the active app unchanged.

- [ ] Finish with the preserved native execution method's whole-branch review,
  fix concrete findings with RED/GREEN verification, commit the verified work,
  and report remaining activation and step-3/4 scope honestly. No push, PR merge,
  or app activation without separate authorization.

## Self-review and decisions

- Scope: every approved design section is covered by Tasks 1–6. All five Review
  Focus cases have named assertions in the owning task.
- Interfaces: CatalogEntry and scope contracts are established before the rewrite,
  selector and provider tasks; only Task 5 consumes them in the durable graph.
- Versioning: corpus 3, rewrite 2 and answer 3 are independent. Existing NLP policy
  stays unchanged. Frozen v1/v2 source hashes and immutable migrations are explicit.
- Provenance ruling: record answer prompt version per event instead of changing
  one global export label, preventing false version claims on historical recovery.
- Test-safety ruling: use a private owned temporary PostgreSQL cluster for actual
  v2-prefix upgrade tests; never downgrade/reset shared test storage or app data.
- Selection rulings: deduplicate cross-category related groups, and request a
  narrower question when an eligible category has no whole group that can fit.
- Execution: native in this session, preserving the prior selected method. No
  delegated implementation. The user approved native execution on 2026-11-02.
