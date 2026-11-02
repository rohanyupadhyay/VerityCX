# RAG Retrieval Regression Cases — Step 3

## Intent and agreed direction

Protect the retrieval behavior added in steps 1 and 2 against regressions in
English plurals, paraphrases, category questions, conversational follow-ups and
unsupported requests. Expected evidence and response behavior come from the
project-authored synthetic policies, rather than whatever the current engine
happens to return.

The user asked to implement step 3, continued after the recommended approach was
presented, and approved this design on 2026-11-02. Proceed with offline regression cases plus a separately
invoked live-model suite. Live execution remains an explicit paid opt-in; this
design does not authorize paid execution, app changes, push or merge.

## Current implementation

- The approved v3 corpus contains 40 synthetic documents. Preserve their bytes,
  section IDs, manifest identity and existing approval state.
- The frozen grounding fixture has exactly 40 cases, and its deterministic
  provider answers exact authored questions. Preserve that contract.
- Existing native tests cover rewrite reservation, same-conversation history,
  category coverage, citations, ambiguity, topic changes and recovery through
  targeted examples. They lack a shared inventory of linguistic variations.
- The current live grounding command records 40 structural outcomes, but does
  not judge retrieval against the broader step-3 cases.
- Step 2 left two nonblocking test gaps: combined multi-category selection at a
  related-group budget boundary, and native recovery/re-export of a completed
  historical result without changing unknown prompt provenance.

## Approaches

1. **Offline cases only:** stable CI checks using real normalization, WordNet,
   category selection and native storage, with explicit scripted model outputs.
   These establish retrieval and control behavior but cannot validate the live
   model's interpretation of unfamiliar wording.
1. **Offline cases plus opt-in live execution — selected recommendation:** reuse
   the same authored scenarios and expected outcomes for repeatable CI and a
   separate run through the actual rewrite/answer providers. This adds provider
   orchestration and reporting, while keeping paid execution outside default CI.

No new testing framework, language dependency or model judge is proposed. Use
the existing Python, pytest, Pydantic, PostgreSQL and provider adapters.

## Scenario inventory

Proposed size: **24 scenarios, 31 submitted turns**, split as follows. Counts and
scenario wording are the builder's proposed defaults, not prior user wording.

| Family | Scenarios | Turns | Coverage |
|---|---:|---:|---|
| Plurals | 4 | 4 | Card/cards and fee/fees; ordinary auxiliary words do not become sufficient evidence |
| Paraphrases | 6 | 6 | Replacement charges, foreign-use fees, opening deposits and other documented policy facts |
| Broad product questions | 5 | 5 | Original cards question, alternate cards wording, savings, accounts, and accounts plus cards |
| Follow-ups | 5 | 12 | Resolved Cedar reference (2); topic change then follow-up (3); ambiguous Cedar/Hazel reference (2); missing antecedent (1); two interleaved conversations (4) |
| Unsupported requests | 4 | 4 | Unknown product, undocumented business eligibility, unsupported attribute of a known product, and genuinely absent subject matter |

Case IDs remain stable and descriptive. Every scenario declares its family,
ordered turns, conversation membership and expected behavior. The two
interleaved conversations must be tested with the same owner so conversation
isolation is demonstrated independently of owner isolation; existing owner
boundary tests remain in force.

Use only authored synthetic facts. The original cards overview must include
policy-03, policy-08 and policy-16. The Cedar replacement fee is 7 synthetic
dollars; the Hazel foreign fee is 2 percent. Verify every expectation against
its source document before freezing it. Do not copy upstream benchmark tasks
or answers.

## Expectations and boundaries

Keep scenario inputs, offline scripted provider outputs and expected outcomes
separate. Never generate expected document IDs from the selector under test.
Validate fixture IDs, conversation references, source references, categories and
bounds before starting a run. Do not amend expectations simply to make a failing
implementation pass.

Expectations can specify required and forbidden document/section IDs, permitted
selected IDs, response kinds, category scope and coverage. Use exact sets for
fully covered small categories. For bounded larger categories, assert membership,
required category representation and honest truncation instead of freezing an
arbitrary tie order. Do not require exact rewritten strings or verbatim answer
phrasing when multiple valid formulations exist.

Unsupported questions may still retrieve lexically similar documents. That is
not evidence for the unsupported product or qualifier. Distinguish an expected
empty retrieval from nonempty but insufficient evidence; the latter must not
become an easier answer about another product. Missing or genuinely ambiguous
antecedents must clarify without an answer call. Provider errors are execution
failures, not successful abstentions.

For successful results, verify citations belong to selected evidence and include
required support. Category answers retain the fixed non-exhaustive scope note
inside the existing output budget. Scripted responses prove publication/control
behavior only; actual factual fidelity requires live output review.

## Offline verification

1. **Retrieval checks:** run the real pinned English normalizer and WordNet
   expander, plus the actual focused/category selector, over approved synthetic
   sources. Cover raw wording variants as appropriate; a frozen rewrite is
   explicitly identified where interpretation is being replayed.
1. **Native pipeline checks:** accept and claim owned test conversations, invoke
   the actual durable worker pipeline with explicit scripted rewrite/answer
   providers, and inspect committed results and rewrite diagnostics. Assert
   original input and same-conversation completed history reach the rewriter,
   selected evidence reaches the answer provider, scopes do not leak across
   turns, and each knowledge turn retains its call budgets. Never teach a fake
   provider the assertion result and describe that as semantic correctness.
1. **Two deferred boundaries:** add a multi-category case where prior allocation
   leaves one section slot before a two-document related group; defer both and
   preserve truthful coverage. Add native recovery of a completed historical
   result whose prompt version is null; invoke no provider, preserve the result
   and audit row, and export `unknown` rather than the current prompt version.
   Model historical state through owned fixtures, without downgrading storage.

The new regression inventory must not expand the production deterministic
provider's exact 40-case contract or change how production questions are routed.
Run new default CI checks through the existing pytest discovery and gates.

## Opt-in live suite

Expose the scenarios through the maintained validation command under a distinct
retrieval-regression suite. An offline invocation is the default; `--live` is the
only way that invocation may select actual OpenAI adapters. Support selection of
named scenarios so a paid smoke can be small. Invalid IDs and missing opt-in,
credentials or dedicated storage fail before model calls.

Use the actual durable worker pipeline with the configured answer and rewrite
models, the real approved test corpus, and fresh owned conversation identities.
HTTP/browser coverage is not implied by a direct worker-pipeline run. Reuse
existing API/ownership tests for that boundary. Keep expected answers and fixture
provider outputs completely outside live rewrite/answer requests. Prior turns
in a live scenario come from actual completed responses, not injected gold
assistant text.

Preserve one rewrite attempt capped at 10 seconds, at most two answer attempts
and a 60-second per-turn database deadline. Retain six evidence sections,
2000 characters per section, 12,000 evidence characters, 16,000 history
characters and an 8000-character final answer. At most 31 turns means at most
93 provider requests under the existing per-turn limits; no automatic scenario
reruns or external model judge. A chosen subset lowers that cap.

Use only the dedicated test database and test corpus namespace. Claim work for
the run's owned conversations; never scan unrelated owners' jobs. Test-only
preparation/approval must not activate or alter the running app's corpus. Do not
purge unrelated records, change credentials, restart the app or send Chatwoot
messages. Close only resources created by this run.

## Results and interpretation

Produce a separate verdict for each tested boundary: rewrite/scope contract,
retrieved support, published disposition/citations and execution status. A failed
live case returns a nonzero exit status and remains visible; never silently
substitute a scripted result or retry a case until it passes.

Stdout contains bounded, sanitized metadata: case IDs, verdicts, selected/cited
IDs, coverage, actual model identities and available usage. Include corpus,
ranking, NLP policy and rewrite/answer prompt versions for reproducibility.
Missing usage/cost stays unknown. Never print credentials, DSNs, raw exceptions,
questions, histories, policy bodies or generated answer text there.

Write a private, ignored local per-run report for inspecting the synthetic
questions, observed rewrites, generated answers, citation IDs, expected authored
facts and verdicts. Create it with private directory/file permissions; no raw
credential-bearing exception payloads. This is the material a person reviews
for factual fidelity. Successful automated checks must still report semantic
review as pending. Match the existing live-grounding convention: a live command
with pending human semantic acceptance does not return an acceptance-success
exit code, even when all automated assertions pass; distinguish that condition
from failed cases in its report.

This step supplies cases and correctness assertions. Comparative baseline
scores, improvement claims, repeated statistical evaluation, latency/cost
optimization, embeddings and reranking remain step 4.

## Implementation scope and handoff

This is a bounded test/validation project. Likely changes are a strict authored
scenario fixture and loader, pytest retrieval/native regressions, validation
runner/reporting support, CLI contracts and the corresponding documentation.
Helper names and file boundaries are left to the implementation plan. Reuse
existing owned-resource helpers where safe; no dependency or product UI change.

Keep the active app and source-policy inventory unchanged throughout development.
Create a feature branch and follow the existing native execution preference.
Verify new checks can detect intentionally wrong retrieval, lost context,
incorrect citations and mislabeled historical provenance before claiming
regression protection. Fix concrete correctness regressions within existing
contracts; do not add a dictionary, semantic search, change retrieval policy,
relax performance targets or hide a failing expectation to obtain green tests.
Record any larger uncovered limitation explicitly for the next increment.

After design approval, write the implementation plan, run the maintained checks
against dedicated test resources, and perform the required final branch review.
Paid live execution, app activation and branch integration remain separately
authorized actions.

## Builder check

A fresh read-only software-engineering check found nothing important left
unanswered for implementation planning. The scenario counts and file boundaries
remain proposed defaults and builder choices as stated above. The user approved
the design on 2026-11-02; implementation planning follows that approval.
