<!-- Documents the knowledge module's implemented interfaces and current limits. -->

# knowledge

Approved document ingestion and bounded lexical retrieval.

## Retrieval version 3

category_retrieval.select_scoped_evidence dispatches the typed rewrite scope.
Focused questions keep the version-2 selector unchanged. Overviews use the approved
catalog index, whose categories and original full-document titles match the bank
pages. Category membership can include a policy without a lexical hit, such as Pine.
Round-robin category allocation covers complete related-title groups before adding
extra sections, keeping six sections and 12,000 characters. Groups that do not fit
are deferred intact. A document without citable passages remains omitted, as does
its entire related group; coverage reports this limitation rather than inventing
a passage. Nonempty categories with no fitting group request a narrower question.
Empty categories abstain without global fallback or an answer call.

Category diagnostics count eligible and represented documents, not the number or
completeness of real bank products. Metadata never supplies policy facts.

## Preserved lexical baseline

The original retrieve function remains the frozen version-1 baseline.
The select_evidence path uses spaCy English lemmas and reviewed stopword overrides
across original/rewritten query concepts, document titles, and passage bodies.
It preserves constraints and product modifiers while preventing constraint-only
relevance. WordNetExpander runs only after empty primary selection, respects POS
and sense grouping, excludes protected/multiword terms, and permits at most three
alternatives per concept and twelve in total. A shared reader is serialized across
worker threads. These lexical tools never supply banking evidence.

Negation includes straight and curly apostrophe contractions. Protected product
terms survive stopword removal, and protection applies across every occurrence of
a concept in the original and rewritten queries. A bounded passage-only cache
holds at most 4096 representations per normalizer; queries and history are never
cached, and source bytes are still verified for every retrieval.

resources.py verifies exact installed package and model/archive bytes; nlp.py loads
the required tagger/lemmatizer components once and batches inference off the worker
event loop. The maintained setup helper installs data before requests; it never
silently downloads or repairs assets during retrieval.

Version-2 manifests bind language-resource and normalization identity. Version-3
manifests also bind the shared category policy and catalog index. Both legacy
hash rules stay unchanged; public browsing supports all three versions without
loading NLP. Chat requires an explicitly approved version-3 corpus.
Dedicated test-database processes use a fixed test corpus cache, protecting the
normal app's active corpus.
Management preparation, approval, and runtime reads share this namespace selection.
Parent-side validation metadata reads explicitly select the same test namespace,
even when the parent has no runtime database environment. Official live validation
requires its separately reviewed test-cache corpus as well.

`documents.py` parses closed id/title/content JSON from at most 1 MiB of verified bytes.
`manifest.py` prepares immutable hash inventories and activates only explicitly approved unchanged
hashes. `index.py` emits deterministic heading/paragraph sections capped at 2000 characters.
`retrieval.py` applies the reviewed log-weighted lexical overlap, stable ID ties, six-section/12000
character evidence cap and 16000-character contiguous prior context. `configuration.py` resolves
only fixed synthetic/official roots and checks official Git provenance without reading banking data.
`models.py` defines strict document, evidence and manifest contracts.

`configuration.active_documents(mode)` and `manifest.load_documents` return complete
approved source documents after verifying the manifest, hashes, identifiers, and section
inventory. `catalog.py` projects these into public categories, matching excerpts, related
titles, and explicitly known synthetic conflict pairs. Unclassified titles remain in
Other policies; category metadata never changes source facts. No upstream documents are
copied into tracked frontend files. Both full-document publication and chat retrieval
fail closed when approval is missing or sources change.

Prepare with `uv run python scripts/manage_support.py corpus prepare --mode synthetic`, then review
and run `uv run python scripts/manage_support.py corpus approve --hash HASH`. Artifacts live under
ignored `.cache/support/corpora/`. Source changes fail closed; no automatic approval, embeddings,
web fetching, task evaluation or banking-record reads. The derived index is not trusted on restore;
verified source bytes reconstruct sections. Live grounding review remains pending.

Dependencies are pinned in root `pyproject.toml`; install with `uv sync --locked --link-mode=copy`.
Run `uv run ruff check src/veritycx/knowledge`, `uv run mypy` and
`uv run pytest tests/support -m "not support_db and not live"` from the repository root.
Native database tests additionally require the dedicated test runtime/admin DSNs described in
[quickstart](../../../../specs/002-durable-knowledge-support/quickstart.md).
