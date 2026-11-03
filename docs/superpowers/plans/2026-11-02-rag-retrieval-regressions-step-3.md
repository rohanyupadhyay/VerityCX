# RAG Retrieval Regression Cases — Step 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Preserve the existing native execution preference; no delegated implementation is selected.

**Goal:** Add 24 authored scenarios covering 31 turns, with independently checked
retrieval/publication contracts, repeatable offline CI and explicitly opt-in live validation.

**Architecture:** Separate scenario inputs and expected outcomes from scripted
provider outputs. Exercise the real selectors and durable worker pipeline; judge
observations outside provider requests. A guarded child process isolates CLI runs
to test storage, returning sanitized metadata and a private semantic-review report.

**Tech Stack:** Existing Python 3.12, pytest, Pydantic, spaCy, NLTK/WordNet,
PostgreSQL 18.6, LangGraph and OpenAI adapters. No new dependency.

**Spec:** [Approved design](../specs/2026-11-02-rag-retrieval-regressions-step-3-design.md),
approved by the user on 2026-11-02. Branch: feat/rag-retrieval-regressions-step-3.
The user has already selected native execution in this session; preserve it.

## Global constraints

- English only. Preserve the exact 40 synthetic source documents, section IDs,
  approved v3 corpus and frozen 40-case deterministic grounding-provider contract.
- One rewrite attempt capped at 10 seconds; at most two answer attempts and a
  60-second per-turn database deadline. No automatic scenario reruns or model judge.
- Six evidence sections, 2000 characters per section, 12,000 evidence characters,
  16,000 history characters and an 8000-character final answer remain unchanged.
- The bundled inventory is 24 scenarios/31 turns; at most 93 provider requests.
  Named subsets may reduce the bound; duplicate selections must not multiply it.
- Run database tests serially against the dedicated veritycx_support_test database.
  Do not reset/downgrade shared storage, purge unrelated rows or scan unrelated jobs.
- Preserve the running app, app database, active corpus pointer, credentials and
  frontend. Only test preparation/approval and owned test identities are permitted.
- Expected facts and scripted provider outputs never enter live model requests.
  Live history consists of actual completed responses from the same conversation.
- Default CI is offline. Paid live execution, app activation, push and merge
  require separate authorization; approval of this plan does not authorize them.
- Stdout contains sanitized metadata only. Detailed synthetic review material stays
  in ignored private files; no credentials, DSNs or raw exceptions are written there.
- Comparative scoring, performance optimization, embeddings and reranking remain
  step 4. Do not relax the existing five-second load target or change retrieval policy.

## Review focus

- A fake returning its authored answer must not conceal missing evidence or context:
  Task 2 detector mutations and Task 3 missing-Pine/lost-history checks must fail.
- Two conversations belonging to one owner must not share antecedents: Task 3
  interleaves Cedar and Hazel, checking exact role-separated completed history.
- Lexically similar evidence for an unsupported product must not count as support:
  Tasks 1–3 distinguish nonempty-but-insufficient evidence from empty retrieval.
- Parent app configuration or inherited tracing must not redirect a validation run:
  Task 4 child-environment and live-gate tests pin test namespace and no integrations.
- A live automated pass must not imply semantic acceptance, and a failed case must
  not disappear into a success summary: Task 4 exit/report/privacy contracts cover both.

## File boundaries and interfaces

| Task | Files | Responsibility |
|---|---|---|
| 1 | New service/retrieval_cases.py and two fixtures; unit/test_retrieval_cases.py | Strict inputs, expectations and separate replay data |
| 2 | New service/retrieval_checks.py; unit/test_retrieval_regressions.py; existing unit/test_category_retrieval.py | Observations, independent verdicts and real selector cases |
| 3 | New service/retrieval_providers.py and retrieval_runner.py; integration/test_retrieval_regressions.py and test_historical_prompt_recovery.py | Recording/replay adapters and actual durable execution |
| 4 | New service/retrieval_reports.py and retrieval_command.py; extend retrieval_providers.py and scripts/validate_support.py; unit/test_retrieval_reports.py, contract/test_retrieval_regressions_cli.py and integration/test_retrieval_live_contract.py | Guarded subprocess, live adapters, reports and CLI |
| 5 | Relevant READMEs and this plan/design execution records | Complete verification and handoff |

Service files above are under src/veritycx/service; test files are under
tests/support. Fixtures are tests/support/fixtures/retrieval-regressions.json and
retrieval-replays.json. Existing production retrieval/provider contracts stay intact.

## Task 1: Authored scenarios and strict separate fixture contracts

**Produces:** retrieval_cases.py defines frozen ClosedModel/VersionedModel types:

- EvidenceExpectation(required_documents, allowed_documents, forbidden_documents,
  required_sections): unique string tuples; allowed_documents may be None.

- RetrievalProbe(scope: SearchScope, expected: EvidenceExpectation,
  empty: bool | None): apply to the original raw question, explicitly using authored scope.

- TurnExpectation(rewrite_kinds, scopes, result_kinds, evidence,
  required_citations, coverage, minimum_category_documents, require_scope_note,
  required_facts). Rewrite kinds are search/clarify; result kinds answer/clarify/abstain;
  scopes are SearchScope tuples; coverage is CategoryCoverage | None; category minima
  map CategoryKey to integers 0..6. All sequences are distinct and bounded.

- RegressionTurn(id, conversation, question, expected, probe: RetrievalProbe | None).
  IDs/aliases use lowercase letters, digits and hyphens, at most 80 characters;
  question is nonblank and at most 8000 characters.

- RegressionScenario(id, family, conversations, turns): family is one of plurals,
  paraphrases, broad, followups, unsupported; one/two declared aliases; 1..4 turns.

- RegressionSet(schema_version=1, provenance, scenarios): at most 24 scenarios and
  31 turns, unique scenario IDs and unique turn IDs within each scenario; every
  turn refers to a declared alias, every alias is used, and the set is nonempty.

- ReplayTurn(case_id, turn_id, rewrite: RewriteResult, answer: ProviderResult | None)
  and ReplaySet. Model labels are scripted-rewrite-v1 and scripted-answer-v1.

- load_cases() -> RegressionSet; select_cases(cases: RegressionSet,
  case_ids: Sequence[str] | None) -> tuple[RegressionScenario, ...];
  validate_case_sources(cases: RegressionSet, manifest: CorpusManifest) -> None;
  load_replays(cases: RegressionSet, manifest: CorpusManifest)
  -> dict\[tuple[str, str], ReplayTurn\]. Use fixed repository-owned paths only.

- [x] Write test_retrieval_cases.py first: assert 24 scenarios, 31 turns and family
  scenario counts 4/6/5/5/4; select_cases rejects unknown/duplicate IDs and retains
  catalog order; reject extra/duplicate JSON keys, unknown aliases/categories,
  duplicate turn IDs and nonexistent source references. Assert replay keys are a
  bijection over the 31 turns, with no replay payload on model-free branches.
  Confirm the existing fixture_cases() still returns exactly 40 original cases.

- [x] Run uv run pytest tests/support/unit/test_retrieval_cases.py -q.
  Expected: RED missing retrieval_cases interfaces, before implementing them.

- [x] Implement the types/loaders and author both JSON fixtures independently.
  Validate source references against manifest entries/section IDs. Do not construct
  expectations from current selector output or have replay providers read them.
  Freeze this inventory, verifying each fact against its source:

  | IDs | Questions/sequence | Expected support and behavior |
  |---|---|---|
  | plural-cedar-card, plural-cedar-cards | Tell me about the Cedar card/cards | policy-03; answer citing policy-03:0001 |
  | plural-hazel-fee, plural-hazel-fees | What is/are the Hazel foreign fee/fees? | policy-08; answer citing policy-08:0001 |
  | para-cedar-replacement | How much is a new Cedar card after losing mine? | policy-03; 7 synthetic dollars |
  | para-hazel-abroad | Using Hazel abroad, what extra charge applies? | policy-08; 2 percent |
  | para-alder-opening | How much do I need to start Alder savings? | policy-01; 50 synthetic dollars |
  | para-dogwood-cash | How much cash can I withdraw each day at a Dogwood ATM? | policy-04; 300 synthetic dollars |
  | para-elm-cutoff | When must I send an Elm wire? | policy-05; 14:00 local time |
  | para-grove-statements | How often are Grove statements sent? | policy-07; monthly |
  | broad-cards-original | What cards does VerityCX offers? | overview cards; exactly 03/08/16 |
  | broad-cards-options | What card options are available? | overview cards; exactly 03/08/16 |
  | broad-savings | What savings products are documented? | overview savings; exactly 01/06/17 |
  | broad-accounts | What account policies are documented? | six of 02/07/09/11/14/15/19; coverage 7/6/truncated |
  | broad-accounts-cards | Which accounts and cards are documented? | six documents: three accounts and all three cards; coverage 10/6/truncated |
  | followup-cedar | Cedar replacement fee -> its replacement fee | 2 turns, policy-03 both |
  | followup-topic-change | Cedar fee -> Alder opening deposit -> its opening deposit | 3 turns, 03 then 01 then 01 |
  | followup-ambiguous | Cedar and Hazel card fees -> What is its fee? | 2 turns: 03/08 then clarify without answer call |
  | followup-missing | What is its replacement fee? | 1 turn: clarify, no retrieval/answer call |
  | followup-interleaved | A:Cedar fee, B:Hazel fee, A:its replacement fee, B:its foreign fee | 4 turns, same owner/two conversations; 03/08/03/08 |
  | unsupported-product | What is the Martian asteroid vault fee? | similar fee evidence may exist; abstain/clarify, no invented fee |
  | unsupported-business | Which VerityCX cards are eligible for businesses? | cards evidence may exist; abstain/clarify, no easier product list |
  | unsupported-attribute | What cryptocurrency insurance does the Cedar card include? | preserve Cedar/qualifier; abstain/clarify |
  | unsupported-absent | What is the quasar hyperdrive warranty? | raw focused probe empty; pipeline abstain/clarify |

  In the table, numeric IDs abbreviate policy-NN. Successful overviews require
  their scope note; all answer facts/citations are authored from the source.
  Search expectations apply only when the observed rewrite searches; clarification
  instead requires no selected evidence or answer attempt. Unsupported live cases
  need not retrieve zero documents to pass; the raw empty probe is a separate check.

- [x] Re-run the task tests. Expected: GREEN; Ruff and strict typing on the new
  module/test also pass. Commit the tested fixture/loader deliverable.

## Task 2: Independent judgments, raw retrieval cases and budget boundary

**Consumes:** Task 1 cases/expectations, actual SearchScope/coverage and corpus index.
**Produces:** retrieval_checks.py defines:

- CallRecorder: mutable typed lists of rewrite requests/results and answer
  requests/results, preserving per-attempt order and explicit absent/error results.

- ObservedTurn: frozen dataclass with case_id/turn_id (fixture IDs), result:
  TurnResult | None, rewrite: RewriteResult | None, rewrite_requests,
  answer_requests, answer_results, rewrite_row: RewriteRow | None,
  selected_sections: tuple[EvidenceSection, ...], answer_attempts: int,
  elapsed_ms: int and execution_error: str | None.

- BoundaryVerdict(status: pass/fail/not_run, reasons: tuple[str, ...]) and
  TurnVerdict(rewrite, retrieval, publication, execution), with passed: bool.
  Reasons are finite server-authored labels, never exception or provider text.

- judge_turn(turn: RegressionTurn, observed: ObservedTurn, \*,
  expected_history: tuple[ContextMessage, ...], catalog_index: Sequence[CatalogEntry])
  -> TurnVerdict. Include execution status even if other checks cannot run.

- ScenarioResult(case_id: str, turns: tuple\[tuple[ObservedTurn, TurnVerdict], ...\])
  and RegressionRun(mode, metadata, scenarios),
  preserving observations/verdicts and explicit dependent not-run turns.

- [x] Write unit/test_retrieval_regressions.py before the judgment implementation.
  Pin tests rejecting wrong/missing evidence, forbidden/out-of-set documents,
  false coverage, wrong citation, lost/foreign history, changed original input,
  incorrect disposition, missing scope note and exhausted budgets. An error must
  not pass as abstention, and a failed turn must make RegressionRun fail.

- [x] Run that module: expected RED missing judgment interfaces.

- [x] Implement independent checks from fixture expectations and observations.
  Compare the exact original question and role-separated expected completed
  same-conversation messages. All scenario histories fit within 16,000 characters;
  assert that bound and compare the full expected list independently of the
  production recent_context helper, so a broken helper cannot alter the oracle. Compare journal-selected IDs
  with actual answer evidence, not just one or the other. Enforce citation
  membership/required support and scope/count honesty against the approved index.
  Treat semantic fact checking as pending, not substring-based model grading.

- [x] Parameterize real raw probes across standalone scenarios with the pinned
  TextNormalizer/WordNetExpander and select_scoped_evidence; no fake NLP. Require
  the expected policy IDs and test that the query "does" yields no evidence.
  Empty results alone may invoke WordNet; overviews must not use it. Do not assert
  an arbitrary focused ranking tie or force unsupported evidence to be empty.

- [x] Add test_multicategory_related_pair_is_deferred_with_one_slot_remaining
  to unit/test_category_retrieval.py. Construct five earlier singleton groups
  across accounts/cards, then a lower-priority two-document related group with
  one member in each category. Assert both pair members absent, five represented,
  seven eligible, coverage truncated, no duplicate selections and stable ordering.
  This adds coverage to existing behavior; no production change is expected.

- [x] Run uv run pytest tests/support/unit/test_retrieval_cases.py
  tests/support/unit/test_retrieval_regressions.py
  tests/support/unit/test_category_retrieval.py -q. Expected: GREEN, including
  deliberately corrupted observations producing failed verdicts. Commit.

## Task 3: Replay/recording providers and actual native pipeline regressions

**Produces:** retrieval_providers.py contains RecordingRewriter(delegate, recorder)
and RecordingAnswer(delegate, recorder), implementing the existing protocols
without changing calls, retries or payloads. ReplayRewriter(replay: ReplayTurn)
and ReplayAnswer(replay: ReplayTurn) return fixed authored results; neither reads
expectations. It also supplies replay_provider_factory(replays:
Mapping\[tuple[str, str], ReplayTurn\]) -> ProviderFactory. retrieval_runner.py supplies:

- ProviderFactory is defined in retrieval_providers.py to avoid circular imports:
  Callable\[[RegressionScenario, RegressionTurn], tuple[QueryRewriter, KnowledgeProvider]\].

- async exercise_regressions(pool: DatabasePool, settings: Settings,
  scenarios: Sequence[RegressionScenario], \*, manifest: CorpusManifest,
  evidence: Sequence[EvidenceSection], providers: ProviderFactory,
  mode: Literal["offline", "live"]) -> RegressionRun.

- Native execution requires the process runtime DSN/test namespace already set
  to the dedicated database; reject incompatible configuration before accepting
  work. It does not load dotenv or start an unscoped worker loop.

- [x] Write integration/test_retrieval_regressions.py against these interfaces.
  Run the full 24-scenario/31-turn inventory offline with real storage, RAG
  dependencies, Repository.accept/claim and process_job; use fresh owners and
  conversations, with one owner per scenario and two aliases in the interleaved one.
  Assert all verdicts pass; exactly one rewrite per attempted knowledge turn,
  at most two answer attempts, and zero answer calls after rewrite clarification
  or empty retrieval. Verify 03/08/16 and scope note for the original question.

- [x] Run that module. Expected: RED missing runner/providers.

- [x] Implement scoped sequential execution; claim only the current conversation.
  Initialize one owned normalizer/WordNet/inference bundle before claiming work,
  reuse it across the run and close only that run's inference capacity. Do not
  close the shared memoized deterministic_rag instance used by other tests.
  Gather committed TurnResult, RewriteRow, attempt counts and selected sections.
  Compute expected history from actual prior completed results in that alias.
  Continue on terminal contract failures to retain actual history; if execution
  leaves a conversation unusable, mark its dependent turns not_run and fail the
  scenario. Preserve unaffected scenarios/aliases. No scenario-level retries.
  Record configured models separately from adapter-reported model metadata;
  unavailable observed identities/usage remain unknown rather than invented.

- [x] Add native detector tests: monkeypatch graph.select_scoped_evidence to omit
  Pine while retaining the other cards, and graph.recent_context to return ().
  The original-card and follow-up/interleaved runs must respectively report
  missing evidence and history mismatch, despite scripted answers being available.
  Restore monkeypatches; ordinary runs remain green. These are controlled tests
  of the detector, not changes to expected outcomes or production policy.

- [x] Add integration/test_historical_prompt_recovery.py: commit an owned result
  with null audit prompt_version, expire only its owned job lease, reclaim with a
  new fence, and call process_job with providers that fail if invoked. Assert no
  provider calls, unchanged completed result and audit provenance, finished job,
  and export_result through a mock TraceExporter emits unknown, not knowledge-v3.
  Never downgrade a database or overwrite any unrelated row. Existing guards
  should pass this added coverage without a production implementation change.

- [x] Run uv run pytest tests/support/integration/test_retrieval_regressions.py
  tests/support/integration/test_historical_prompt_recovery.py
  tests/support/integration/test_category_rag.py
  tests/support/integration/test_rewrite_recovery.py -q.
  Expected: GREEN against maintained dedicated test storage. Commit.

## Task 4: Guarded live/offline CLI and private review reports

**Produces:** retrieval_reports.py defines public_summary(run: RegressionRun)
-> dict[str, object] and write_review_report(run: RegressionRun) -> Path.
retrieval_command.py defines run_regressions(env: Mapping[str, str], \*,
live: bool = False, case_ids: Sequence[str] | None = None) -> dict[str, object]
and a fixed module child entry point. Add live_provider_factory(client:
AsyncOpenAI, settings: Settings) -> ProviderFactory in retrieval_providers.py.
CLI adds --suite retrieval and repeatable
--case ID, valid only with that suite. Existing offline/grounding/demo behavior stays.

- [x] Write unit/test_retrieval_reports.py and
  contract/test_retrieval_regressions_cli.py first. Assert raw questions, histories,
  body/answer/exception/credential/DSN canaries are absent from stdout summaries;
  private review data contains the required synthetic material and no raw errors.
  Assert report directories/files use private 0700/0600 permissions on POSIX and
  remain under the fixed ignored evidence root, with fresh non-overwriting run IDs.
  Unknown/duplicate cases, missing live credentials and app/unsafe DSNs must fail
  before model construction, database writes or child startup.
- [x] Run the new modules. Expected: RED missing CLI/report interfaces.
- [x] Implement the parent orchestration and fixed owned subprocess. Validate
  cases and dedicated storage first with existing dedicated_database (only
  veritycx_support_test on literal 127.0.0.1/::1, with its existing option allowlist),
  then use child-only runtime DSN equal to
  VERITYCX_TEST_DATABASE_URL, test corpus namespace, tracing disabled and no
  migration or Chatwoot credentials. Offline children receive no OpenAI key;
  they never reload root dotenv. Parent environment/files stay unchanged.
  Capture child output; only a validated bounded summary may reach parent stdout.
  Never forward raw child stderr on failure. Close only the child handle owned by
  this invocation; interruption must terminate/reap it.
- [x] The child prepares/approves only test-synthetic and verifies schema 3 before
  work. Load the fixed support.toml Settings with explicit execution provider;
  retain configured model/rewrite_model and all existing budgets. Offline loads
  only the separate replay file; live never loads replays or passes expectations
  to a provider. Construct one AsyncOpenAI client with max_retries=0 and existing
  OpenAIQueryRewriter/OpenAIProvider adapters for live operation. No external
  trace exporter, Chatwoot bridge, browser, API server or unscoped work loop.
- [x] Produce public case/boundary verdicts, IDs, scope/coverage, versions, model
  metadata and available usage; cost stays null when unavailable. The fixed
  private directory is .cache/support/evidence/retrieval-regressions/<run-uuid>/,
  with review.json containing synthetic inputs, actual rewrites/results, expected
  authored facts and citation IDs. Never include credentials or raw exceptions.
  Semantic review remains pending, and evidence_kind distinguishes scripted/live.
- [x] Pin exits: 0 for offline automated pass; 1 for failed cases or execution;
  2 for live automated pass with semantic acceptance still pending. Do not treat
  not_run/dependent failures or provider errors as successful abstention. Report
  case failures individually; never rerun them implicitly.
- [x] Test real SDK mock transports through the live path with no paid network.
  Assert expected facts/replay payloads never appear in requests, while actual
  completed response history does; assert one rewrite and bounded answers.
  Place native mock-live coverage in integration/test_retrieval_live_contract.py
  marked support_db, using live_provider_factory with a real SDK client backed by
  its mock HTTP transport. Parent/child CLI contracts may stub the child boundary.
  A sentinel load_replays must never run in live mode. Test child isolation with
  parent app DSN/active pointer and tracing/key canaries, plus cleanup on failure.
  Use spies or temporary stand-ins for a bad parent pointer; never edit the actual
  app pointer, even temporarily, to test isolation.
  New ordinary tests must not carry the live marker or require real credentials.
- [x] Run uv run pytest tests/support/unit/test_retrieval_reports.py
  tests/support/contract/test_retrieval_regressions_cli.py
  tests/support/integration/test_retrieval_live_contract.py
  tests/support/contract/test_validation_cli.py
  tests/support/contract/test_environment_commands.py -q.
  Then run uv run python scripts/validate_support.py --suite retrieval
  against dedicated test storage: expected exit 0, 24 scenarios/31 turns and
  evidence_kind scripted. Commit. Do not run --live without separate authorization.

## Task 5: Documentation, maintained checks and native branch handoff

**Files:** README.md, scripts/README.md, src/veritycx/service/README.md,
tests/support/README.md, fixtures/README.md, affected unit/integration/contract
READMEs, docs/README.md, this plan and the approved design execution record.

- [x] Document inventory, raw/replay/live distinctions, guard prerequisites,
  private review material, exit 0/1/2, named subsets and the 93-request ceiling.
  Explain pending semantic review and step-4 boundaries; preserve dated evidence.
  No app migration, source reapproval or frontend rebuild is required by this work.

- [x] Run all maintained commands from the repository root:

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

  Native tests
  require dedicated runtime/admin test DSNs; never print them. If needed, run
  setup_support_local.py without --app to update only test storage. Expected:
  all checks pass; unchanged 30-turn load target p95 \<= 5 seconds, zero leaks,
  one-second scan cadence. Record any failure before a justified retry.

- [x] Run the standalone commands serially: uv run python scripts/validate_support.py
  --suite offline, then --suite retrieval. Expected: exit 0 for each, existing
  knowledge/handoff outcomes plus all 24 new scenarios/31 turns. Test named
  offline --case broad-cards-original selects exactly one scenario/one turn.
  No actual paid live test is part of this implementation gate.

- [x] Verify unchanged 40-case grounding fixture and source manifest hash
  327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c; app cache/
  environment are untouched. Establish test-only database usage through DSN and
  scope guards, without querying customer records. Report control-flow evidence honestly.

- [x] Perform the preserved native method's one fresh whole-branch review;
  regrade and fix concrete Critical/Important findings with RED/GREEN evidence,
  retain the ledger's rulings/minors in the committed execution record, and
  commit verified work. No push/merge/activation without separate authorization.

## Self-review and decisions

- Coverage: every design section maps to Tasks 1–5; all five Review Focus lines
  have explicit detector, isolation or privacy tests in the owning task.
- Native preference is preserved. Task 1 contracts precede observations/judgment,
  which precede the native runner and guarded CLI; no circular task dependencies.
- Child-process isolation is a builder decision: graph corpus resolution reads
  process configuration, so CLI runs need their own test-only environment.
- Scripted outputs are stored separately and never used by the live factory;
  expectations remain judge-only. Exact rewrite/answer wording is not a live oracle.
- Exit 2 for pending live review is a builder decision consistent with the design's
  non-success requirement; existing grounding/demo exit behavior remains intact.
- The two deferred boundaries are test-only additions to existing correct guards;
  do not fabricate a missing production feature to manufacture RED. New fixture,
  judge, runner and CLI code each has its own observed failing test cycle.
- Existing immutable source, schema, language and prompt policies do not change.
  No production retrieval tuning or semantic-search implementation is hidden here.
- The user approved this plan for native implementation on 2026-11-02.

## Verification record (2026-11-02)

- Baseline: 445 database-free tests passed, 111 deselected, one existing warning.
- Focused task gates: 12 fixture checks; 57 independent/raw-selector checks;
  14 native inventory/recovery checks; 31 CLI/report/mock-live checks passed.
- Maintained lock, resource, environment, Ruff (192 files), strict mypy
  (168 files), Markdown and two workflow YAML checks passed. A supplemental
  narrow mypy invocation omitted the source tree and reported eight untyped
  imports; the full scan then identified one package import corrected to an
  explicit module import. No type suppression or source-layout change was made.
- Full offline suite: **625 passed**, one existing Starlette/AnyIO deprecation
  warning, 394.55 seconds. The unchanged 30-turn load gate measured p95
  **4.882664 seconds**, zero leaks, one-second scan cadence and five-second target.
- The first standalone offline validator failed `offline_checks_failed`. Its
  new failing-test cache entry was
  `tests/support/acceptance/test_load.py::test_deterministic_load`; its exact
  inner exception/client p95 was not retained by the existing driver. A stale
  uncollected Chatwoot cache entry predated this run and was not a new failure.
- An unchanged isolated load diagnostic passed at p95 **2.604949 seconds**,
  30 turns and zero leaks. The standalone gate was retried once without changing
  runtime code, cadence, concurrency, caching or target. The retry passed its
  subprocess checks, three knowledge and six handoff cases.
- Both new standalone retrieval invocations passed: 24 scenarios/31 turns and
  the named original-cards subset of one scenario/one turn. Offline evidence is
  explicitly scripted; actual live-path tests use intercepted SDK transports.
- The 40 source entries, original 40 grounding cases and v3 manifest hash
  `327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c`
  are unchanged. A read-only check confirmed the app environment digest was
  unchanged and readiness returned HTTP 200. Test guards target dedicated storage.
- No paid acceptance run, app migration/activation, push or merge was performed.
  Local timing variability and pending human semantic review remain explicit.
  Final whole-branch review follows these completed implementation/test gates.

The standalone retry load evidence measured p95 **4.937324 seconds**,
with zero leaks; this does not establish a production latency guarantee.

## Final review and fix pass (2026-11-03)

The fresh whole-branch review used gpt-6-astra against the complete branch
package, approved design and this plan. The implementation owner accepted all
three Important findings; there were no Critical findings. One fix pass follows
the native execution method, with no second review.

- Isolation: inherited libpq connection defaults could redirect the test child.
  The owned child now drops inherited PG-prefixed variables while pinning the
  validated test DSN; the parent is unchanged. A hostile-environment contract
  failed first and passed after the fix. PostgreSQL documents these defaults in
  its [environment reference](https://www.postgresql.org/docs/current/libpq-envars.html)
  and [connection reference](https://www.postgresql.org/docs/current/libpq-connect.html).
- Evidence: correct IDs could conceal changed bodies, hashes, titles or corpus
  identity, and provider-facing coverage was not independently checked. The
  checker now compares complete evidence objects with approved corpus sections
  and provider coverage with catalog truth. Five unit mutations failed first
  and passed after the fix. An additional native wrong-body mutation confirms
  that scripted answers cannot conceal changed source bodies; its first
  invocation lacked the test DSN and was rerun with explicit test configuration.
- Storage: create/accept/claim/observation failures could abort the whole run.
  Four injected boundary failures reproduced that loss after an earlier complete
  scenario. The runner now retains earlier observations and actual provider
  requests/results, fails the affected turn, marks its dependents unrun and
  continues independent aliases/scenarios. Failed observation has no claimed
  durable result; its attempt count records actual captured answer calls.
  Both report forms sanitize storage exceptions, with no automatic rerun.

The focused post-fix gate passed 55 tests in 54.46 seconds. Ruff and full strict
mypy passed. The evidence/isolation fixes are committed as 19289e0; structured answer-output
retention follows in cb9a3f6. The final full-suite and standalone
results are recorded below after execution.

## Execution rulings carried from the native ledger

- Ruling: preserve the existing feature checkout and declared direct-workspace preference — the worktree skill honors an existing preference and the approved plan preserves native/current-checkout execution — cost: no filesystem isolation; mitigate through test-only storage, unchanged source documents and no app activation.
- Ruling: partial-overview replay answers may filter a finite authored claim inventory by supplied evidence — fixed full answers would freeze an arbitrary valid six-of-seven selection — cost: these replay outputs adapt to input, so gold coverage checks and missing-evidence detector tests remain independent; no semantic/live claim is made. ReplayTurn.available_claims_only is explicit and limited to authored answers.
- Ruling: use explicit What/Which grammar for the multi-category and two unsupported retrieval scenarios, preserving their gold outcomes — the approved design forbids changing production routing and allows builder-selected wording; the original cards regression remains verbatim — cost: imperative Show, Does-only and noun-only intake variants still clarify before retrieval and remain a documented limitation for step4. Unsupported-business gold permits focused or cards-overview scope when the qualifier is preserved; disposition still must abstain/clarify.
- Final: Ruling: live-model factual fidelity remains pending — paid execution is excluded from this approved implementation; mock SDK contracts verify wiring only — cost: actual model answer fidelity is unverified until an authorized live run and human semantic review.
- Final: Ruling: broader intake-language behavior remains outside this change — production routing stays unchanged and limitations are documented — cost: Show/Does-only/noun-only variants can clarify before retrieval.
- Final: Ruling: production latency guarantees and comparative retrieval gains remain step4 work — local gates check regressions without claiming measured production improvement — cost: load timing remains variable and no comparative gain has been established.
- Final: minor (deferred): add an authored candidate-fact inventory to private partial-account overview reports; current reports expose questions, citations and actual outputs but incomplete expected account facts. Manual reviewers can consult cited policies.

## Verification-discovered readiness defect

Two complete post-review runs failed only the unchanged load test:
634 passed/one failed in 457.43 seconds, then 635 passed/one failed in
437.91 seconds after the additional report-retention test. Both failures were
latency_target_failed; their exact p95 was not retained by the old validator.
An isolated load/report gate passed 14 tests, including load p95 2.705550 seconds.
No failing result was discarded or target relaxed.

Root-cause investigation reproduced the order dependency with just knowledge
validation immediately followed by load: one passed/one failed in 25.82 seconds.
Finite numeric exception diagnostics measured p95 5.312660 seconds; first turns
were 5.009–5.316 seconds and later turns 2.112–2.431 seconds. Readiness accepted a
fresh heartbeat left by the terminated preceding worker while the new scoped
worker was still initializing NLP resources.

The scoped load harness now assigns its own worker UUID and waits for that exact
heartbeat as well as HTTP readiness. Optional identity plumbing preserves worker
defaults and has no CLI/configuration, schema, retrieval-policy or running-app
change. A native foreign-fresh-heartbeat guard failed before the fix; the guard
and identical knowledge→load sequence then passed all three tests in 27.82 seconds,
with load p95 2.674839 seconds, 30 turns, zero leaks and one-second scans. No warmup
turn, cache change, concurrency change or five-second target change was made.
This verification fix is committed as d938b61. Final Ruff checks cover 193 files
and strict typing covers 169 files. One new test initially used an implicit
module.time reexport, corrected to a direct stdlib import without a suppression.

- Final: Ruling: bind load-harness readiness to its explicitly owned worker identity — the maintained gate must not accept the preceding validation worker's heartbeat while this worker initializes NLP; this is test readiness correctness, not retrieval/performance tuning — cost: a small optional worker-identity plumbing surface and startup readiness wait; cold startup duration is not included in post-readiness turn latency, while the five-second target, one-second scan, concurrency and caches remain unchanged.

## Final verified state (2026-11-03)

- The final code tree at d938b61 passed **637 tests**, one existing
  Starlette/AnyIO deprecation warning, in **443.85 seconds**. Its 30-turn load
  measurement was p95 **2.595527 seconds**, zero leaks and one-second scans.
- All maintained static checks passed: lock, retrieval resources, environment
  contract, Ruff (193 files), strict mypy (169 files), Markdown and both workflow
  YAML checks. Final documentation formatting is checked before its commit.
- Standalone commands passed serially: offline knowledge **3** and handoff **6**;
  retrieval **24 scenarios/31 turns**; named original-cards **1 scenario/1 turn**.
  All three exits were zero, and retrieval evidence remains explicitly scripted.
- The standalone support suite load measured p95 **2.898918 seconds**,
  30 turns, zero leaks and one-second scans. Earlier failures and the readiness
  correction remain recorded above; these timings are not a production guarantee.
- All three Important review findings have RED→GREEN evidence and a green full
  suite. The additional Important readiness defect was reproduced with a
  knowledge→load sequence and fixed through an owned-worker guard. No second
  review was dispatched. The single Minor finding remains deferred above.
- The 40 source documents, original 40 grounding cases and corpus hash
  327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c
  are unchanged, as is support configuration. No paid acceptance run, app
  migration/activation/restart, push or merge was performed. Live-model semantic
  acceptance remains pending, and step4 measurement remains a separate increment.

The seven rulings and one deferred Minor above preserve the execution ledger.
All implementation tasks and global verification gates are complete; branch
integration requires the user's separate choice.
