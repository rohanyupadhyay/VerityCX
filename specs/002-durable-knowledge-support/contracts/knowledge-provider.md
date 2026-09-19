<!-- Defines approved document access, deterministic retrieval and interchangeable provider contracts. -->

# Knowledge and Provider Contract

## Permitted Sources

Official mode consumes only the Feature 001 configured documents subtree from its exact tag/commit.
The acquisition/check command is a developer prerequisite. The support runtime does not invoke the
full acquisition inspector or read banking `db.json`, evaluation tasks, upstream source or examples.
It consumes the reviewed derived manifest and document bytes bounded to that subtree.

The corpus administration command validates the existing checkout using the existing developer
workflow, prepares a hash manifest and requires explicit local approval before activation. Manifest
entries bind source classification, path and hash to the pinned commit. Approval never expands the
allow-list. No arbitrary alternate source path is accepted in production configuration.
Synthetic mode uses only the fixed project-authored fixture directory and a visibly synthetic corpus
identity; it cannot be presented as official data or selected by a remote customer.

Inspect every path component without following links, reject symlinks/reparse points/special files
and confirm containment before opening. Validate JSON UTF-8 envelope with exactly string id/title/
content fields. Unknown/duplicate fields, duplicate IDs and files above 1 MiB fail the build.
Recheck file identity and hashes during use; use only the verified bytes for parsing. A detected
source/manifest change yields corpus_changed; no automatic repair or mixed-version retrieval.

Source classification relies on the pin and reviewed manifest, not a promise that a text classifier
can detect all disguised evaluation material. Deny-canary tests must prove a moved/renamed forbidden
artifact cannot enter via path, unknown schema, changed hash or manifest substitution. Unknown
production content is rejected for review rather than automatically promoted to knowledge.

## Section Index and Retrieval

Normalize content into heading/paragraph sections, retaining document title and heading path.
Split sections above 2,000 code points on paragraph/word boundaries, with deterministic ordinal
anchors and no overlap. Record source hash, parser version and section hash. No upstream content
or generated index is committed; output lives in `.cache/support/corpora/<manifest-hash>/`.

Tokenize case-folded Unicode word tokens; score normalized query-token overlap weighted by inverse
document frequency, summed per section. For N indexed sections, use
`sum(log(1 + N / (1 + df(token))))` over unique query tokens present in a section, where df is the
number of sections containing that token. Tokenization uses Unicode alphanumeric runs, excludes
underscores, and applies casefold; no stopword list or stemming. Sort descending by score, then stable document/section ID.
Return at most six positive-score sections and at most 12,000 evidence code points; zero score
returns no evidence. The formula and tokenization are versioned in index metadata and golden tests.
Do not interpret links as permission to fetch more documents or URLs.

Context includes the current message plus the most recent completed conversation turns fitting
16,000 code points, retaining order and role boundaries; older messages remain in storage and GET
history but may be excluded from model context. If omitted context is needed, request clarification.
Do not silently summarize older policy claims into new evidence. No cross-conversation memory store.

## Routing and Policy

The LangGraph routing node is deterministic: prioritize explicit requests for a human, then
unavailable account/transaction intent, then ambiguous or mixed intent, then knowledge queries.
Version the English intent rules and test paraphrases, negation and mixed requests. Ambiguous cases
clarify, never authorize operations. The API has an explicit resume operation; a chat sentence cannot
consume a pause or modify ownership.

The security node checks workflow permission before retrieval. Independent source checks constrain
retrieval, and output checks constrain publication. Operational tools are absent from both adapters.
Poor intent classification may reduce answer quality but must not grant any forbidden capability.

## Provider Protocol

An async `KnowledgeProvider` protocol accepts a closed ProviderRequest and returns a closed
ProviderResult or categorized failure. The request contains question, selected evidence with IDs,
bounded prior context, opaque correlation ID and budget. No owner credentials, filesystem handle,
network tool, database handle, fence or mutable graph state is supplied.

The result disposition is answer, clarify or abstain. An answer contains one or more claim objects
with nonempty text and evidence IDs; clarify/abstain have bounded text and no purported supported
claims. Total response text is at most 8,000 code points. Validate every evidence ID against the
selected sections, not the full corpus. Render citations server-side from the manifest. Reject
extra state/tool/authorization fields; output validation may abstain rather than publish bad claims.

Deterministic adapter: finite project-authored scenarios keyed by fixture inputs, with configurable
failure injection available only to test code. It proves control-flow contracts, not model quality.
Live adapter: OpenAI Responses, configured snapshot `gpt-4.1-mini-2025-04-14`, structured schema,
no tools, `store=false`, `max_output_tokens=2048`, SDK retries zero. The SDK uses httpx2;
adapter test transport types must match the pinned SDK, while service tests use httpx.
Every outgoing call passes through the attempt ledger; no hidden repair/model calls are permitted.

Unknown usage is nullable, never reported as zero. Provider/model and prompt/schema versions are
recorded with results. Live mode is explicit and requires credentials; absence must fail clearly,
not silently fall back to synthetic output. Provider errors are normalized without storing raw bodies.

## Grounding Acceptance

Freeze 40 synthetic document/question cases before the live run. Each supported case identifies
required policy facts and admissible supporting sections; unsupported cases require abstention;
ambiguous/conflicting cases require a question or conflict disclosure. Human review marks a
supported answer passing only if all substantive claims have entailing sources and all required
facts are correct, with no contradictory additions. Apply SC-001 thresholds exactly.

Offline tests cover deterministic ranking, schema validation, missing sources, changed hashes and
the six adversarial categories. They do not substitute for the live grounding review. Evidence
records contain case IDs, outcome/rubric and configuration; official document bodies and evaluation
answers remain excluded from tracked artifacts.
