# Offline retrieval comparison

Generated: 2026-11-03T13:01:15.908536+00:00. Run: 6474c5d1-955b-47d9-9837-52e1ec0dc482.

This is a known-regression component comparison, not held-out evaluation and not answer correctness.
Raw questions use authored scopes; the scripted_rewrite track supplies authored queries and scopes.
All versions receive the same original-plus-query text. The v1 algorithm is retained, but this is
not a reconstruction of its historical whole-system behavior. No models or database are invoked.

The spaCy pipeline and WordNet reader are shared. Passage caches are separate per input/version.
Uncached passage timing measures the first selector call after language initialization; warmed
timing repeats the same input with its passage cache populated. Neither is production turn latency.
Shared language setup: 2979.431 ms. Warm repetitions per input/version: 5.

## Quality

Means include only labeled cases; each cell shows its own denominator. — means unmeasured.
Required recall/rank use only explicitly required documents, not a complete relevance judgment.
Allowed precision/coverage use unique documents and only cases with an authored allowed set.
Partial overviews can meet the contract while covering six of seven or six of ten documents.

| Track | Version | Inputs | Assessed / passed | Unassessed / errors | Required recall | Required RR | Allowed precision | Allowed coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw | v1 | 19 | 17 / 12 | 2 / 0 | 0.844 (n=15) | 0.867 (n=15) | 0.750 (n=4) | 0.390 (n=5) |
| scripted_rewrite | v1 | 29 | 26 / 22 | 3 / 0 | 0.907 (n=25) | 0.920 (n=25) | 0.750 (n=4) | 0.390 (n=5) |
| raw | v2 | 19 | 17 / 13 | 2 / 0 | 0.933 (n=15) | 1.000 (n=15) | 0.867 (n=5) | 0.604 (n=5) |
| scripted_rewrite | v2 | 29 | 26 / 22 | 3 / 0 | 0.960 (n=25) | 1.000 (n=25) | 0.867 (n=5) | 0.604 (n=5) |
| raw | v3 | 19 | 17 / 17 | 2 / 0 | 1.000 (n=15) | 0.967 (n=15) | 1.000 (n=5) | 0.891 (n=5) |
| scripted_rewrite | v3 | 29 | 26 / 26 | 3 / 0 | 1.000 (n=25) | 0.980 (n=25) | 1.000 (n=5) | 0.891 (n=5) |

## Paired contract differences

Improved means v3 passes a labeled contract the baseline fails; regressed is the reverse.
Unchanged includes both passing and failing ties. Unassessed/error pairs are excluded explicitly.

| Track | Baseline → v3 | Improved | Regressed | Unchanged | Unassessed |
| --- | --- | --- | --- | --- | --- |
| raw | v1 → v3 | 5 | 0 | 12 | 2 |
| raw | v2 → v3 | 4 | 0 | 13 | 2 |
| scripted_rewrite | v1 → v3 | 4 | 0 | 22 | 3 |
| scripted_rewrite | v2 → v3 | 4 | 0 | 22 | 3 |

## Retrieval timing

Cells are median ms / nearest-rank p95 ms / actual timing samples. Repeats do not increase quality n.
Variant order rotates across inputs and repetitions. Measurements are serial and machine-specific.

| Track | Version | Uncached passages | Warmed |
| --- | --- | --- | --- |
| raw | v1 | 0.351 / 0.533 / 19 | 0.352 / 0.570 / 95 |
| scripted_rewrite | v1 | 0.370 / 0.630 / 29 | 0.370 / 0.734 / 145 |
| raw | v2 | 49.457 / 131.007 / 19 | 3.501 / 9.004 / 95 |
| scripted_rewrite | v2 | 50.082 / 63.000 / 29 | 3.439 / 5.607 / 145 |
| raw | v3 | 48.272 / 54.431 / 19 | 3.491 / 8.524 / 95 |
| scripted_rewrite | v3 | 48.878 / 56.693 / 29 | 3.335 / 5.288 / 145 |

## Family breakdown

Nonempty retrieval on unsupported questions is descriptive, not an unsupported-answer failure.
Only explicit expected-empty labels can establish an empty-result contract violation.

| Track | Version | Family | Inputs | Assessed / passed | Unassessed / errors | Unsupported nonempty | Explicit empty labels / violations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| raw | v1 | broad | 5 | 5 / 1 | 0 / 0 | 0 | 0 / 0 |
| raw | v1 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| raw | v1 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| raw | v1 | unsupported | 4 | 2 / 1 | 2 / 0 | 3 | 1 / 1 |
| scripted_rewrite | v1 | broad | 5 | 5 / 1 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v1 | followups | 10 | 10 / 10 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v1 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v1 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v1 | unsupported | 4 | 1 / 1 | 3 / 0 | 3 | 0 / 0 |
| raw | v2 | broad | 5 | 5 / 1 | 0 / 0 | 0 | 0 / 0 |
| raw | v2 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| raw | v2 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| raw | v2 | unsupported | 4 | 2 / 2 | 2 / 0 | 3 | 1 / 0 |
| scripted_rewrite | v2 | broad | 5 | 5 / 1 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v2 | followups | 10 | 10 / 10 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v2 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v2 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v2 | unsupported | 4 | 1 / 1 | 3 / 0 | 3 | 0 / 0 |
| raw | v3 | broad | 5 | 5 / 5 | 0 / 0 | 0 | 0 / 0 |
| raw | v3 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| raw | v3 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| raw | v3 | unsupported | 4 | 2 / 2 | 2 / 0 | 3 | 1 / 0 |
| scripted_rewrite | v3 | broad | 5 | 5 / 5 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v3 | followups | 10 | 10 / 10 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v3 | paraphrases | 6 | 6 / 6 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v3 | plurals | 4 | 4 / 4 | 0 / 0 | 0 | 0 / 0 |
| scripted_rewrite | v3 | unsupported | 4 | 1 / 1 | 3 / 0 | 3 | 0 / 0 |

## Case results

| Track | Case / turn | Version | Contract | Returned documents | Reasons |
| --- | --- | --- | --- | --- | --- |
| raw | plural-cedar-card / t1 | v1 | pass | policy-03, policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| raw | plural-cedar-card / t1 | v2 | pass | policy-03, policy-08 | — |
| raw | plural-cedar-card / t1 | v3 | pass | policy-03, policy-08 | — |
| scripted_rewrite | plural-cedar-card / t1 | v1 | pass | policy-03, policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| scripted_rewrite | plural-cedar-card / t1 | v2 | pass | policy-03, policy-08 | — |
| scripted_rewrite | plural-cedar-card / t1 | v3 | pass | policy-03, policy-08 | — |
| raw | plural-cedar-cards / t1 | v1 | pass | policy-03, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| raw | plural-cedar-cards / t1 | v2 | pass | policy-03, policy-08 | — |
| raw | plural-cedar-cards / t1 | v3 | pass | policy-03, policy-08 | — |
| scripted_rewrite | plural-cedar-cards / t1 | v1 | pass | policy-03, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| scripted_rewrite | plural-cedar-cards / t1 | v2 | pass | policy-03, policy-08 | — |
| scripted_rewrite | plural-cedar-cards / t1 | v3 | pass | policy-03, policy-08 | — |
| raw | plural-hazel-fee / t1 | v1 | pass | policy-08, policy-02, policy-03, policy-11, conflict-01-a, conflict-01-b | — |
| raw | plural-hazel-fee / t1 | v2 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| raw | plural-hazel-fee / t1 | v3 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| scripted_rewrite | plural-hazel-fee / t1 | v1 | pass | policy-08, policy-02, policy-03, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | plural-hazel-fee / t1 | v2 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| scripted_rewrite | plural-hazel-fee / t1 | v3 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| raw | plural-hazel-fees / t1 | v1 | pass | policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| raw | plural-hazel-fees / t1 | v2 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| raw | plural-hazel-fees / t1 | v3 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| scripted_rewrite | plural-hazel-fees / t1 | v1 | pass | policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| scripted_rewrite | plural-hazel-fees / t1 | v2 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| scripted_rewrite | plural-hazel-fees / t1 | v3 | pass | policy-08, policy-02, policy-03, policy-11 | — |
| raw | para-cedar-replacement / t1 | v1 | pass | policy-03, policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| raw | para-cedar-replacement / t1 | v2 | pass | policy-03, policy-08 | — |
| raw | para-cedar-replacement / t1 | v3 | pass | policy-03, policy-08 | — |
| scripted_rewrite | para-cedar-replacement / t1 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | para-cedar-replacement / t1 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | para-cedar-replacement / t1 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| raw | para-hazel-abroad / t1 | v1 | pass | policy-08, policy-01, policy-02, policy-03, policy-04, policy-05 | — |
| raw | para-hazel-abroad / t1 | v2 | pass | policy-08, policy-01, policy-02, policy-03, policy-04, policy-05 | — |
| raw | para-hazel-abroad / t1 | v3 | pass | policy-08, policy-01, policy-02, policy-03, policy-04, policy-05 | — |
| scripted_rewrite | para-hazel-abroad / t1 | v1 | pass | policy-08, policy-03, policy-02, policy-11, policy-01, policy-04 | — |
| scripted_rewrite | para-hazel-abroad / t1 | v2 | pass | policy-08, policy-03, policy-02, policy-11, policy-01, policy-04 | — |
| scripted_rewrite | para-hazel-abroad / t1 | v3 | pass | policy-08, policy-03, policy-02, policy-11, policy-01, policy-04 | — |
| raw | para-alder-opening / t1 | v1 | pass | policy-01, policy-06, policy-17, policy-02, policy-03, policy-04 | — |
| raw | para-alder-opening / t1 | v2 | pass | policy-01, policy-06, policy-17 | — |
| raw | para-alder-opening / t1 | v3 | pass | policy-01, policy-06, policy-17 | — |
| scripted_rewrite | para-alder-opening / t1 | v1 | pass | policy-01, policy-06, policy-10, policy-12, policy-17, policy-02 | — |
| scripted_rewrite | para-alder-opening / t1 | v2 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| scripted_rewrite | para-alder-opening / t1 | v3 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| raw | para-dogwood-cash / t1 | v1 | pass | policy-04, policy-09 | — |
| raw | para-dogwood-cash / t1 | v2 | pass | policy-04, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| raw | para-dogwood-cash / t1 | v3 | pass | policy-04, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a | — |
| scripted_rewrite | para-dogwood-cash / t1 | v1 | pass | policy-04, policy-09, policy-12 | — |
| scripted_rewrite | para-dogwood-cash / t1 | v2 | pass | policy-04, policy-12, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| scripted_rewrite | para-dogwood-cash / t1 | v3 | pass | policy-04, policy-12, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| raw | para-elm-cutoff / t1 | v1 | pass | policy-05 | — |
| raw | para-elm-cutoff / t1 | v2 | pass | policy-05 | — |
| raw | para-elm-cutoff / t1 | v3 | pass | policy-05 | — |
| scripted_rewrite | para-elm-cutoff / t1 | v1 | pass | policy-05, policy-18 | — |
| scripted_rewrite | para-elm-cutoff / t1 | v2 | pass | policy-05, policy-18 | — |
| scripted_rewrite | para-elm-cutoff / t1 | v3 | pass | policy-05, policy-18 | — |
| raw | para-grove-statements / t1 | v1 | pass | policy-07 | — |
| raw | para-grove-statements / t1 | v2 | pass | policy-07 | — |
| raw | para-grove-statements / t1 | v3 | pass | policy-07 | — |
| scripted_rewrite | para-grove-statements / t1 | v1 | pass | policy-07 | — |
| scripted_rewrite | para-grove-statements / t1 | v2 | pass | policy-07 | — |
| scripted_rewrite | para-grove-statements / t1 | v3 | pass | policy-07 | — |
| raw | broad-cards-original / t1 | v1 | fail | conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a, conflict-03-b | missing_evidence, outside_allowed_evidence, coverage_mismatch |
| raw | broad-cards-original / t1 | v2 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| raw | broad-cards-original / t1 | v3 | pass | policy-03, policy-08, policy-16 | — |
| scripted_rewrite | broad-cards-original / t1 | v1 | fail | conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a, conflict-03-b | missing_evidence, outside_allowed_evidence, coverage_mismatch |
| scripted_rewrite | broad-cards-original / t1 | v2 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| scripted_rewrite | broad-cards-original / t1 | v3 | pass | policy-03, policy-08, policy-16 | — |
| raw | broad-cards-options / t1 | v1 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| raw | broad-cards-options / t1 | v2 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| raw | broad-cards-options / t1 | v3 | pass | policy-03, policy-08, policy-16 | — |
| scripted_rewrite | broad-cards-options / t1 | v1 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| scripted_rewrite | broad-cards-options / t1 | v2 | fail | policy-03, policy-08 | missing_evidence, coverage_mismatch |
| scripted_rewrite | broad-cards-options / t1 | v3 | pass | policy-03, policy-08, policy-16 | — |
| raw | broad-savings / t1 | v1 | pass | policy-01, policy-06, policy-17 | — |
| raw | broad-savings / t1 | v2 | pass | policy-01, policy-06, policy-17 | — |
| raw | broad-savings / t1 | v3 | pass | policy-01, policy-06, policy-17 | — |
| scripted_rewrite | broad-savings / t1 | v1 | pass | policy-01, policy-06, policy-17 | — |
| scripted_rewrite | broad-savings / t1 | v2 | pass | policy-01, policy-06, policy-17 | — |
| scripted_rewrite | broad-savings / t1 | v3 | pass | policy-01, policy-06, policy-17 | — |
| raw | broad-accounts / t1 | v1 | fail | policy-11, policy-15 | coverage_mismatch |
| raw | broad-accounts / t1 | v2 | fail | policy-11, policy-15, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | outside_allowed_evidence, coverage_mismatch |
| raw | broad-accounts / t1 | v3 | pass | policy-11, policy-15, policy-02, policy-07, policy-09, policy-14 | — |
| scripted_rewrite | broad-accounts / t1 | v1 | fail | policy-11, policy-15 | coverage_mismatch |
| scripted_rewrite | broad-accounts / t1 | v2 | fail | policy-11, policy-15, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | outside_allowed_evidence, coverage_mismatch |
| scripted_rewrite | broad-accounts / t1 | v3 | pass | policy-11, policy-15, policy-02, policy-07, policy-09, policy-14 | — |
| raw | broad-accounts-cards / t1 | v1 | fail | empty | missing_evidence, coverage_mismatch |
| raw | broad-accounts-cards / t1 | v2 | fail | policy-03, policy-08, policy-11, policy-15 | missing_evidence, coverage_mismatch |
| raw | broad-accounts-cards / t1 | v3 | pass | policy-11, policy-03, policy-15, policy-08, policy-02, policy-16 | — |
| scripted_rewrite | broad-accounts-cards / t1 | v1 | fail | empty | missing_evidence, coverage_mismatch |
| scripted_rewrite | broad-accounts-cards / t1 | v2 | fail | policy-03, policy-08, policy-11, policy-15 | missing_evidence, coverage_mismatch |
| scripted_rewrite | broad-accounts-cards / t1 | v3 | pass | policy-11, policy-03, policy-15, policy-08, policy-02, policy-16 | — |
| scripted_rewrite | followup-cedar / t1 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-cedar / t1 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-cedar / t1 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-cedar / t2 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-cedar / t2 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-cedar / t2 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-topic-change / t1 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-topic-change / t1 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-topic-change / t1 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-topic-change / t2 | v1 | pass | policy-01, policy-06, policy-10, policy-12, policy-17, conflict-01-a | — |
| scripted_rewrite | followup-topic-change / t2 | v2 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| scripted_rewrite | followup-topic-change / t2 | v3 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| scripted_rewrite | followup-topic-change / t3 | v1 | pass | policy-01, policy-06, policy-10, policy-12, policy-17, conflict-01-a | — |
| scripted_rewrite | followup-topic-change / t3 | v2 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| scripted_rewrite | followup-topic-change / t3 | v3 | pass | policy-01, policy-06, policy-10, policy-12, policy-17 | — |
| scripted_rewrite | followup-ambiguous / t1 | v1 | pass | policy-03, policy-08 | — |
| scripted_rewrite | followup-ambiguous / t1 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-ambiguous / t1 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t1 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-interleaved / t1 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t1 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t2 | v1 | pass | policy-08, policy-03, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-interleaved / t2 | v2 | pass | policy-08, policy-03, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t2 | v3 | pass | policy-08, policy-03, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t3 | v1 | pass | policy-03, policy-08, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-interleaved / t3 | v2 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t3 | v3 | pass | policy-03, policy-08, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t4 | v1 | pass | policy-08, policy-03, policy-02, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | followup-interleaved / t4 | v2 | pass | policy-08, policy-03, policy-02, policy-11 | — |
| scripted_rewrite | followup-interleaved / t4 | v3 | pass | policy-08, policy-03, policy-02, policy-11 | — |
| raw | unsupported-product / t1 | v1 | unassessed | policy-02, policy-03, policy-08, policy-11, conflict-01-a, conflict-01-b | — |
| raw | unsupported-product / t1 | v2 | unassessed | policy-02, policy-03, policy-08, policy-11 | — |
| raw | unsupported-product / t1 | v3 | unassessed | policy-02, policy-03, policy-08, policy-11 | — |
| scripted_rewrite | unsupported-product / t1 | v1 | unassessed | policy-02, policy-03, policy-08, policy-11, conflict-01-a, conflict-01-b | — |
| scripted_rewrite | unsupported-product / t1 | v2 | unassessed | policy-02, policy-03, policy-08, policy-11 | — |
| scripted_rewrite | unsupported-product / t1 | v3 | unassessed | policy-02, policy-03, policy-08, policy-11 | — |
| raw | unsupported-business / t1 | v1 | unassessed | empty | — |
| raw | unsupported-business / t1 | v2 | unassessed | policy-03, policy-08, policy-06, policy-09, policy-10, policy-13 | — |
| raw | unsupported-business / t1 | v3 | unassessed | policy-03, policy-08, policy-06, policy-09, policy-10, policy-13 | — |
| scripted_rewrite | unsupported-business / t1 | v1 | unassessed | empty | — |
| scripted_rewrite | unsupported-business / t1 | v2 | unassessed | policy-03, policy-08, policy-06, policy-09, policy-10, policy-13 | — |
| scripted_rewrite | unsupported-business / t1 | v3 | unassessed | policy-03, policy-08, policy-06, policy-09, policy-10, policy-13 | — |
| raw | unsupported-attribute / t1 | v1 | pass | policy-03, policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| raw | unsupported-attribute / t1 | v2 | pass | policy-03, policy-08 | — |
| raw | unsupported-attribute / t1 | v3 | pass | policy-03, policy-08 | — |
| scripted_rewrite | unsupported-attribute / t1 | v1 | pass | policy-03, policy-08, conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b | — |
| scripted_rewrite | unsupported-attribute / t1 | v2 | pass | policy-03, policy-08 | — |
| scripted_rewrite | unsupported-attribute / t1 | v3 | pass | policy-03, policy-08 | — |
| raw | unsupported-absent / t1 | v1 | fail | conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a, conflict-03-b | empty_mismatch |
| raw | unsupported-absent / t1 | v2 | pass | empty | — |
| raw | unsupported-absent / t1 | v3 | pass | empty | — |
| scripted_rewrite | unsupported-absent / t1 | v1 | unassessed | conflict-01-a, conflict-01-b, conflict-02-a, conflict-02-b, conflict-03-a, conflict-03-b | — |
| scripted_rewrite | unsupported-absent / t1 | v2 | unassessed | empty | — |
| scripted_rewrite | unsupported-absent / t1 | v3 | unassessed | empty | — |

## Excluded input tracks

These turns remain in the inventory but do not invoke retrieval in the indicated track.

| Track | Case / turn | Reason |
| --- | --- | --- |
| raw | followup-cedar / t1 | no_raw_probe |
| raw | followup-cedar / t2 | no_raw_probe |
| raw | followup-topic-change / t1 | no_raw_probe |
| raw | followup-topic-change / t2 | no_raw_probe |
| raw | followup-topic-change / t3 | no_raw_probe |
| raw | followup-ambiguous / t1 | no_raw_probe |
| raw | followup-ambiguous / t2 | no_raw_probe |
| scripted_rewrite | followup-ambiguous / t2 | authored_clarification |
| raw | followup-missing / t1 | no_raw_probe |
| scripted_rewrite | followup-missing / t1 | authored_clarification |
| raw | followup-interleaved / t1 | no_raw_probe |
| raw | followup-interleaved / t2 | no_raw_probe |
| raw | followup-interleaved / t3 | no_raw_probe |
| raw | followup-interleaved / t4 | no_raw_probe |

## Provenance and reproduction

```bash
uv run python scripts/compare_retrieval.py --repetitions 5
```

- Corpus: synthetic-327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c
- Corpus SHA-256: 327f77dafc86fe6ef60480fcfc3ebc7f3fd75177906860abed74da218bf68d6c
- Fixture SHA-256: 3117b8aeca7f6600d2858e81acd77fd4fce43f8887bac72cf528cf47cf690766
- Replay SHA-256: ecea0ac1b1f27e370abe63fc62b559c7f1bf12ff2f16f1a3f771ff107d9b44d5
- Resource manifest SHA-256: 716d14b9bb8c872e357d479ef22a96dec0f41712595196399d26acce62893e23
- Git revision: d464490ee1e0f0b0e05a366610f2181ccfbed29c; working tree dirty: False
- Python: 3.12.3; platform: linux
- Provider requests: 0; model usage, monetary cost and semantic acceptance: unmeasured.

| Implementation | SHA-256 |
| --- | --- |
| knowledge/retrieval.py | eaa7e8085a66715e9d179c8cd4c226342c2cf411d1ec9a13eecb1af8f3c0e9b9 |
| knowledge/category_retrieval.py | e30d52f1ca36d3a4ba0a3c65a424659e9cabfc3e570cfc28cceb3c87ba1ca5a7 |
| knowledge/nlp.py | b2ec9efae6b88f5c79ced77378777f2fbc59cc0b9e6f895f283c2e678cc1b41b |
| knowledge/synonyms.py | 78eeb5dc33d0dba50a1a84c62df83778fd96978cc7572a2dfcba468d42ccea22 |
| service/retrieval_metrics.py | 658b1b80070588c49b6499dffaf88ed53891d1191d78e4516e2a45c85495c2a3 |
| service/retrieval_comparison.py | 9b2e782c54d214e653da103c14a651aed60949a1838f67aba4a00175db1477f6 |
| service/retrieval_checks.py | ac089775918f6fc1f185a7ff3db534828179492650b4fa3c704cfdcad94eb047 |
| service/retrieval_cases.py | 90ffde1cb2dce7466e99686f067f1868e59cc00654a78389b957194827edda46 |
| knowledge/catalog.py | c64de76212967d105260cc18f48aa9a7eb51b5f4f3d26dc168e1400fade484ab |
| knowledge/manifest.py | 704dccc0507f36c11bb24e49f5ff46ddba8c53a89d105ee9d0ea773a6f6cdc9f |
| knowledge/models.py | 59fabcf37a2c6861443d2c93c16c8856e6ee5a8c3a0021c4f81f4d8cb1e259e8 |
| knowledge/resources.py | b0454c762cf26c18f898740433798dce8729d3f1469816b1bb9c111ad07e718c |
| knowledge/scope.py | eaee19c1bf32813baa65069261aaf66d5aa3daa6e74dcaa90780c1e4547cdc1a |

## Interpretation limits

The fixtures already informed earlier fixes. These are descriptive regression results, not an
independent benchmark or evidence of broad production improvement. Unknown relevance labels
limit precision denominators. Supplied rewrites/scopes cannot validate actual model rewriting,
conversation resolution, unsupported-answer safety or factual fidelity. An embeddings decision
requires additional independently labeled/held-out failures and an explicit comparison feature.
