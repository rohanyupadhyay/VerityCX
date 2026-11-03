# Offline retrieval measurement — RAG step 4

The user accepted proceeding with the recommended offline comparison rather than
continuing design questions. Build and run a reproducible component comparison
before considering semantic search. Preserve the declared native execution and
current-checkout preferences. No paid evaluation, app activation, dependency,
schema, corpus, routing, retrieval-policy or performance-target change is included.

## Comparison

Reuse the frozen 24-scenario/31-turn regression catalog and separate authored
replays. Call the retained v1 keyword, v2 normalized/WordNet and v3 category-aware
retrievers; do not reconstruct their algorithms. All use the same current source
sections and existing six-section/12,000-character caps.

There are two separately reported input tracks:

- Raw: the 19 explicitly authored raw probes, using literal original questions
  and their supplied scopes. Record the other 12 turns as lacking raw probes.
- Scripted rewrite: search dispositions from the authored replays; preserve
  original text and supply the same authored rewritten query to every version.
  Record authored clarification turns separately without invoking retrieval.

The v1 selector receives the union search text (original plus supplied query);
v2/v3 receive those same two strings through their existing interfaces. v1/v2
lack category expansion; v3 consumes the supplied scope. This measures component
behavior with controlled inputs, not historical whole-system behavior, actual
rewrite/history quality, answer correctness or held-out/official performance.
Keep expected evidence outside selector inputs. No provider clients or adapters are instantiated or invoked.

## Quality and honest denominators

Score unique document identities, retaining ordered section IDs for diagnosis.
Report required-document recall and first-required-document reciprocal rank only
where required documents are labeled. Report allowed-document precision and
coverage only where an allowed set exists; empty selections have undefined
precision. Deduplicate multiple sections of one document in document metrics.

Also check required sections, forbidden/outside-allowed documents, explicit raw
empty/nonempty expectations, and overview represented counts/category minima.
Verify complete returned sections against the supplied corpus and preserve caps.
A case without an applicable gold assertion is unassessed, not a passing case.
Unsupported nonempty retrieval is descriptive; it does not prove an unsupported
answer. In particular, a Cedar policy can legitimately support abstaining about
an undocumented Cedar attribute. No new relevance labels are inferred or tuned.

Summaries show counts and metric denominators per version, track and family.
Report paired v3-v1/v2 improved/regressed/unchanged contract outcomes, excluding
unassessed pairs and retaining their excluded count. Repeated timing samples
never multiply the quality sample size. Quality differences are descriptive
known-regression results, not statistical generalization claims.

## Timing

Initialize and time shared verified spaCy/WordNet setup separately. The spaCy
pipeline and WordNet reader are shared in this serial process; only passage
caches are isolated per input and variant. For each
input/version use a separate normalizer passage cache. Time the first selector
call with uncached passages, then 1–20 repeated warmed calls (default 5). Verify
all repeated outputs, including evidence/context, match the first output.
Rotate variant order across cases and repetitions. Report sample counts, median
and nearest-rank p95. These are in-process, serial retrieval timings; they exclude
language-resource startup, database/HTTP queueing and model calls. No production
SLA or latency improvement claim follows from them.

## Command and provenance

Add scripts/compare_retrieval.py with repeatable --case, bounded --repetitions
and optional --markdown PATH. It uses synthetic sources without preparing,
approving or touching any corpus cache, database or environment file. A nonexistent
or duplicate case fails with a fixed error. Resource/setup errors fail safely.
Unexpected selector failures are retained per row and fail command execution;
continue other rows. Current v3 assessed contract failures also return nonzero;
expected earlier-baseline quality failures are valid comparison data.

JSON stdout contains bounded IDs, numeric metrics and provenance only, never
questions, source bodies, credentials or raw exceptions. A Markdown report is
written only to an explicit new path, never overwriting an existing file. Include
corpus hash, fixture/replay/resource and relevant source-code hashes, Git revision
and dirty state, Python/platform, sample policy and explicit component-only limits.
Provider requests are zero; usage/cost and model semantic acceptance are unmeasured.
Generate a dated comparison report under docs/evaluations after implementation.

## Completion

TDD covers partial/unlabeled gold, unique-document metrics, scoped coverage,
failures/determinism, input-track exclusions, order/caps, CLI safety and output
privacy. Run maintained static checks, the full offline suite and actual default
and named-case comparisons. Review the completed branch once, fix Important
findings with reproducing tests, and report the actual measured differences and
remaining limits. Keep the running app unchanged and keep integration separate.
