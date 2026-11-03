# RAG Retrieval Measurement Step 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.
> Preserve native implementation in the current checkout. The user accepted the
> offered offline-first execution without another design discussion; proceed.

**Goal:** Compare retained v1/v2/v3 retrieval fairly and produce an inspectable
report of observed correctness, coverage and retrieval timing differences.

**Architecture:** Add an independent metrics module, component benchmark runner,
and thin standalone CLI/Markdown renderer. Reuse the fixed regression inventory,
source loader, selectors and NLP resources without changing production behavior.

**Tech Stack:** Python 3.12, existing spaCy/NLTK, Pydantic, pytest; no dependencies.

**Spec:** [Offline measurement design](../specs/2026-11-03-rag-retrieval-measurement-step-4-design.md).

## Global Constraints

- No paid provider calls, database access, environment edits, corpus preparation/
  approval, source changes, app restart, push or merge in this increment.
- Same frozen 24 scenarios/31 turns and source sections for all three variants;
  six-section/12,000-character caps and retrieval implementations unchanged.
- Keep raw and authored-rewrite tracks separate; do not claim model/history or
  answer validation from supplied rewrites/scopes. Unassessed is not passing.
- Repetitions default5, allowed1–20; shared NLP setup and uncached passage timing
  separate from warmed median/p95. Timing repetition does not increase quality n.
- JSON contains only IDs, fixed labels, numbers, hashes and version metadata.
  Markdown writes exclusively to an explicit new path; no overwrites.

## Review Focus

1. Incomplete gold must not imply full relevance labels or empty-result safety.
1. Shared NLP caches and selector order must not masquerade as comparative gains.
1. Clarifications, absent raw probes and execution failures must stay visible.
1. Passing replay-fed retrieval must not imply model rewrite or semantic quality.
1. New report paths and command errors must not overwrite files or leak content.

## Task 1: Independent evidence metrics

**Files:** Create src/veritycx/service/retrieval_metrics.py and
tests/support/unit/test_retrieval_metrics.py.

**Interfaces:** Produces EvidenceMetrics and assess_evidence(expected, sections,
scope, catalog_index, expected_empty=None, expected_coverage=None,
minimum_category_documents=None). Metrics expose contract_passed bool|None,
required_document_recall, required_document_rr, allowed_document_precision,
allowed_document_coverage and finite reason labels.

- [x] Write literal tests: two sections of docA count once, required{A,B} with
  selected{A,X} recall0.5/RR1; allowed{A,B} precision0.5/coverage0.5; unknown
  allowed set => null precision; empty selection => null precision, recall0;
  unlabeled => null contract; explicit expected-empty with selected evidence
  fails; overview wrong counts/category balance fails despite allowed IDs.
- [x] Run uv run pytest tests/support/unit/test_retrieval_metrics.py -q.
  Expected RED for missing interface before code; then implement and GREEN.
- [x] Commit feat: add independent retrieval comparison metrics.

## Task 2: Controlled comparison runner

**Files:** Create src/veritycx/service/retrieval_comparison.py and
tests/support/unit/test_retrieval_comparison.py.

**Interfaces:** Consumes Task1 metrics. Produces compare_retrieval(case_ids=None,
repetitions=5)->ComparisonReport, summarize_rows, latency_stats and finite
execution-error rows. Report holds per-case rows, grouped summaries, paired
outcomes, exclusions, provenance and shared_setup_ms; .passed gates only current
v3 assessed failures and execution errors. Markdown/CLI consume this report.

- [x] Test real fixed sources/selectors: raw19 + scripted search turns, explicit
  missing-probe/clarification exclusions, all three variants, same corpus/caps,
  original-cards v3 IDs03/08/16, warmed n/repeat count, family/group denominators,
  no false precision for missing gold and paired failures/unknowns counted.
- [x] Test corrupted selector body/unknown ID, thrown exception, unstable repeated
  output, invalid repetition/case selection: retain rows and fail execution.
  Use literal numeric samples to check median and nearest-rank p95.
- [x] Run uv run pytest tests/support/unit/test_retrieval_comparison.py -q.
  Expected RED, then implement to GREEN. Call actual selectors with controlled
  inputs only; golden evidence never reaches selector arguments. Initialize shared
  resources once, separate per-input/version passage caches and rotate order.
- [x] Commit feat: compare frozen retrieval baselines offline.

## Task 3: CLI, report and measured handoff

**Files:** Create scripts/compare_retrieval.py,
src/veritycx/service/retrieval_comparison_report.py,
tests/support/contract/test_retrieval_comparison_cli.py;
modify scripts/README.md, src/veritycx/service/README.md,
tests/support/unit/README.md, tests/support/contract/README.md, docs/README.md;
create dated docs/evaluations/2026-11-03-retrieval-comparison.md.

**Interfaces:** CLI consumes ComparisonReport; render_markdown(report)->str;
JSON schema stays strictly content-free. Only explicit --markdown writes a file.

- [x] Add actual CLI tests for named-case offline execution with no DB/key,
  bounded/duplicate/unknown arguments, absence of query/body/key canaries in JSON,
  metadata/sample denominators, exclusive Markdown creation and finite errors.
  Test renderer with assessed and unassessed metrics and execution failures.
- [x] Run uv run pytest tests/support/contract/test_retrieval_comparison_cli.py -q.
  Expected RED then implement GREEN. Baseline quality failures alone remain exit0;
  current v3 assessed failures or any execution failure return1.
- [x] Document commands, provenance, warm/cold labels, partial gold, supplied
  rewrite/scope limits and descriptive unsupported retrieval. No embeddings
  decision is justified solely by a known regression set.
- [x] Run maintained lock/resources/environment/Ruff/strict-mypy/Markdown/YAML
  checks and uv run pytest tests -m 'not live' -q, serial test DB usage.
  Expected all pass, unchanged load p95\<=5sec/scan1sec/zero leaks. Retain failures.
- [x] Run full comparison with default5 repetitions and named original-cards
  subset; save JSON privately and a new dated Markdown report. Check actual
  outcomes rather than requiring a positive improvement. Commit feature/docs,
  rerun report after source commit for provenance, then commit measured report.

## Global finishing gate

- [x] Perform one fresh whole-branch review using Review Focus and ledger; fix
  Important findings RED→GREEN with a green full suite. No automatic re-review.
  Preserve all rulings/minors in this plan before removing its scratch directory.

## Execution decisions

The user chose offline-first progress and prior native/direct-workspace preferences
persist. This plan is self-reviewed for source/metric/runner/report interfaces.
Gold labels remain outside selector inputs. Full-code baselines are preserved;
new timing controls never alter production caching or resource initialization.

## Execution rulings

- Ruling: preserve native execution/current checkout and proceed through the recorded plan without another approval round — user said proceed after the explicit offline-first/skip-discussion offer and existing preferences persist — cost: no filesystem isolation or separate design sign-off; mitigate with a feature branch, frozen inputs and no app changes.
- Ruling: separate raw probes from common authored-rewrite/scope component inputs — all variants need controlled inputs and original constraints, while real model interpretation is outside offline scope — cost: results cannot establish end-to-end rewrite/history/answer fidelity or held-out generalization.
- Ruling: treat missing relevance/empty labels as unknown and count unsupported nonempty results descriptively — source retrieval does not establish answerability and focused gold is incomplete — cost: precision and safety denominators are limited; unsupported-answer quality remains unmeasured.

## Verification record (2026-11-03)

- Baseline: 337 database-free support tests passed,123 deselected,1 existing warning.
- Independent metrics RED8→GREEN8; comparison RED9failures/3fixtureerrors→GREEN12,
  then changed-fixture test RED→GREEN; focused combined 31 tests passed in 53.32 seconds.
- Initial six invalid-CLI checks were too weak (a missing script also failed).
  They now require the exact parser/selection category. Inaccessible output
  preflight reproduced an unsanitized PermissionError and passed after the guard.
- Maintained lock/resources/environment/Ruff (200 files), strict mypy (176 files)/Markdown and
  two workflow YAML checks passed. Full offline suite: **668 passed**, one existing
  Starlette/AnyIO warning, **445.56 seconds**. No earlier gate failure was hidden.
- Existing load gate: 30 turns,p95=2.558153seconds, zero leaks, one-second scans and five-second target.
- Final default comparison ran alone after tests on clean source commit
  d464490ee1e0f0b0e05a366610f2181ccfbed29c: 144 variant rows, 14 explicit track
  exclusions, 5 warm samples/input/version,zero provider requests. Named original
  cards subset also passed with 6 rows. The report preserves hashes and unknowns.
- Raw contracts: v1 12/17, v2 13/17, v3 17/17, plus 2 unassessed inputs.
  Authored-rewrite contracts: v1/v2 22/26, v3 26/26, plus 3 unassessed inputs.
  Paired v3 improvements: 5/4 on raw against v1/v2, 4/4 on authored rewrites;
  zero paired contract regressions. These tracks overlap and are not independent
  held-out questions. Initial timing collected during static checks was discarded
  as a final measurement; only the separate quiet run is the dated report.
- App code, retrieval policies, source documents, corpus/schema/configuration and
  credential files were unchanged. The benchmark never opens storage; existing
  native tests use their dedicated database. No paid evaluation, app restart,
  push or merge is included. Final review is the remaining global gate.

## Final review and verified state

The fresh gpt-6-astra whole-branch review found no Critical issues, one Important
parser disclosure and one nonblocking clarification-only reporting gap. Default
argparse errors could echo an unknown option value or unexpected positional text.
Three subprocess canary cases reproduced the disclosure (RED), then passed with
finite parser error categories. Normal help and bounded repetition errors remain
available. All 14 CLI checks passed; Ruff and full strict mypy (176 files) passed.

The complete post-fix suite passed **672 tests**, one existing Starlette/AnyIO
warning, in **456.56 seconds**. No automatic second review was dispatched.
The unchanged 30-turn load gate measured p95 **2.762761 seconds**, zero leaks and one-second scans.

The quiet default comparison and named original-cards comparison were rerun after
tests on clean source commit 611c895. The report was intentionally refreshed from
that new run; the CLI itself still never overwrites an existing report path.
The three retained algorithm implementations and all quality outcomes are unchanged:
raw 12/17,13/17,17/17; authored-query 22/26,22/26,26/26; zero paired regressions.
Unknown/unassessed inputs and 14 exclusions remain explicit. The source commit,
hashes, full timing samples and machine context are in the JSON evidence.

All implementation and global verification gates are complete. The app was not
restarted or changed. Paid-model quality, held-out validation and integration are
outside this approved offline increment.

### Final reviewer exclusions and deferred item

- Final: minor (deferred): valid clarification-only selection has zero rows, two exclusions and exit1 without a finite no_applicable_inputs reason; conservative empty-run gating stands, but document/test that outcome more explicitly later.
- Final: Ruling: actual model rewriting/history/answer factuality remains outside offline comparison — authored inputs intentionally control component inputs — cost: actual model interpretation and answer fidelity remain unverified by these measurements.
- Final: Ruling: unsupported-answer safety remains unmeasured — source presence and incomplete labels cannot establish safe abstention — cost: nonempty unsupported retrieval cannot be interpreted as a false answer or proof of safety.
- Final: Ruling: held-out generalization and the embeddings decision remain deferred — the inventory already informed the fixes — cost: descriptive improvements do not justify broad effectiveness or semantic-search claims.
- Final: Ruling: production latency/concurrency/HTTP/storage/application integration remain outside this benchmark — serial component timings isolate retrieval and the app is unchanged — cost: no production latency/SLA or new integration guarantee follows.
- Final: Ruling: paid usage/cost/provider behavior remains unmeasured — no provider is executed by offline components — cost: model token/cost and provider reliability need a separately scoped evaluation.
- Final: Ruling: baseline relevance weaknesses remain comparison subjects — modifying retained selectors would invalidate the baseline control — cost: baseline failures remain visible rather than fixed in this increment.
- Final: Ruling: reviewer does not independently rerun the full native/static suite — author verification is fresh and the review is read-only with focused code checks — cost: no second independent full-suite execution; author reruns the suite after the Important fix.
