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

- [ ] Add actual CLI tests for named-case offline execution with no DB/key,
  bounded/duplicate/unknown arguments, absence of query/body/key canaries in JSON,
  metadata/sample denominators, exclusive Markdown creation and finite errors.
  Test renderer with assessed and unassessed metrics and execution failures.
- [ ] Run uv run pytest tests/support/contract/test_retrieval_comparison_cli.py -q.
  Expected RED then implement GREEN. Baseline quality failures alone remain exit0;
  current v3 assessed failures or any execution failure return1.
- [ ] Document commands, provenance, warm/cold labels, partial gold, supplied
  rewrite/scope limits and descriptive unsupported retrieval. No embeddings
  decision is justified solely by a known regression set.
- [ ] Run maintained lock/resources/environment/Ruff/strict-mypy/Markdown/YAML
  checks and uv run pytest tests -m 'not live' -q, serial test DB usage.
  Expected all pass, unchanged load p95\<=5sec/scan1sec/zero leaks. Retain failures.
- [ ] Run full comparison with default5 repetitions and named original-cards
  subset; save JSON privately and a new dated Markdown report. Check actual
  outcomes rather than requiring a positive improvement. Commit feature/docs,
  rerun report after source commit for provenance, then commit measured report.
- [ ] Perform one fresh whole-branch review using Review Focus and ledger; fix
  Important findings RED→GREEN with a green full suite. No automatic re-review.
  Preserve all rulings/minors in this plan before removing its scratch directory.

## Execution decisions

The user chose offline-first progress and prior native/direct-workspace preferences
persist. This plan is self-reviewed for source/metric/runner/report interfaces.
Gold labels remain outside selector inputs. Full-code baselines are preserved;
new timing controls never alter production caching or resource initialization.
