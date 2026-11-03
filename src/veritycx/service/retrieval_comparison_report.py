"""Render inspectable comparison evidence with explicit limits and denominators."""

from veritycx.service.retrieval_comparison import ComparisonReport, MetricMean, TimingStats


def _mean(value: MetricMean) -> str:
    return f"{value.value:.3f} (n={value.sample_count})" if value.value is not None else "— (n=0)"


def _timing(value: TimingStats | None) -> str:
    return f"{value.median_ms:.3f} / {value.p95_ms:.3f} / {value.sample_count}" if value else "—"


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def render_markdown(report: ComparisonReport) -> str:
    """Keep missing labels, partial coverage, errors and supplied-input limits visible."""
    p = report.provenance
    lines = [
        "# Offline retrieval comparison",
        "",
        f"Generated: {report.started_at}. Run: {report.run_id}.",
        "",
        (
            "This is a known-regression component comparison, not held-out evaluation and"
            " not answer correctness."
        ),
        (
            "Raw questions use authored scopes; the scripted_rewrite track supplies "
            "authored queries and scopes."
        ),
        (
            "All versions receive the same original-plus-query text. The v1 algorithm is "
            "retained, but this is"
        ),
        (
            "not a reconstruction of its historical whole-system behavior. No models or "
            "database are invoked."
        ),
        "",
        (
            "The spaCy pipeline and WordNet reader are shared. Passage caches are "
            "separate per input/version."
        ),
        (
            "Uncached passage timing measures the first selector call after language "
            "initialization; warmed"
        ),
        (
            "timing repeats the same input with its passage cache populated. Neither is "
            "production turn latency."
        ),
        f"Shared language setup: {p.shared_setup_ms:.3f} ms. "
        f"Warm repetitions per input/version: {p.repetitions}.",
        "",
        "## Quality",
        "",
        (
            "Means include only labeled cases; each cell shows its own denominator. — "
            "means unmeasured."
        ),
        (
            "Required recall/rank use only explicitly required documents, not a complete "
            "relevance judgment."
        ),
        (
            "Allowed precision/coverage use unique documents and only cases with an "
            "authored allowed set."
        ),
        (
            "Partial overviews can meet the contract while covering six of seven or six "
            "of ten documents."
        ),
        "",
        (
            "| Track | Version | Inputs | Assessed / passed | Unassessed / errors | "
            "Required recall | Required RR | Allowed precision | Allowed coverage |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for g in report.groups:
        if g.family == "all":
            cells = [
                _mean(g.metrics[k])
                for k in (
                    "required_document_recall",
                    "required_document_rr",
                    "allowed_document_precision",
                    "allowed_document_coverage",
                )
            ]
            lines.append(
                _row(
                    g.track,
                    g.version,
                    g.input_count,
                    f"{g.assessed_count} / {g.passed_count}",
                    f"{g.unassessed_count} / {g.error_count}",
                    *cells,
                )
            )
    lines += [
        "",
        "## Paired contract differences",
        "",
        "Improved means v3 passes a labeled contract the baseline fails; regressed is the reverse.",
        (
            "Unchanged includes both passing and failing ties. Unassessed/error pairs are"
            " excluded explicitly."
        ),
        "",
        "| Track | Baseline → v3 | Improved | Regressed | Unchanged | Unassessed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for pair in report.pairs:
        lines.append(
            _row(
                pair.track,
                f"{pair.baseline} → v3",
                pair.improved,
                pair.regressed,
                pair.unchanged,
                pair.unassessed,
            )
        )
    lines += [
        "",
        "## Retrieval timing",
        "",
        (
            "Cells are median ms / nearest-rank p95 ms / actual timing samples. Repeats "
            "do not increase quality n."
        ),
        (
            "Variant order rotates across inputs and repetitions. Measurements are serial"
            " and machine-specific."
        ),
        "",
        "| Track | Version | Uncached passages | Warmed |",
        "| --- | --- | --- | --- |",
    ]
    for g in report.groups:
        if g.family == "all":
            lines.append(
                _row(g.track, g.version, _timing(g.uncached_timing), _timing(g.warm_timing))
            )
    lines += [
        "",
        "## Family breakdown",
        "",
        (
            "Nonempty retrieval on unsupported questions is descriptive, not an "
            "unsupported-answer failure."
        ),
        "Only explicit expected-empty labels can establish an empty-result contract violation.",
        "",
        (
            "| Track | Version | Family | Inputs | Assessed / passed | Unassessed / "
            "errors | Unsupported nonempty | Explicit empty labels / violations |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for g in report.groups:
        if g.family != "all":
            lines.append(
                _row(
                    g.track,
                    g.version,
                    g.family,
                    g.input_count,
                    f"{g.assessed_count} / {g.passed_count}",
                    f"{g.unassessed_count} / {g.error_count}",
                    g.unsupported_nonempty_count,
                    f"{g.explicit_empty_count} / {g.explicit_empty_failed_count}",
                )
            )
    lines += [
        "",
        "## Case results",
        "",
        "| Track | Case / turn | Version | Contract | Returned documents | Reasons |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        outcome: str
        if row.error:
            outcome = row.error
        elif row.metrics and row.metrics.contract_passed is not None:
            outcome = "pass" if row.metrics.contract_passed else "fail"
        else:
            outcome = "unassessed"
        reasons = ", ".join(row.metrics.reasons) if row.metrics else "—"
        lines.append(
            f"| {row.track} | {row.case_id} / {row.turn_id} | {row.version} | {outcome} | "
            + (", ".join(row.selected_document_ids) or "empty")
            + f" | {reasons or '—'} |"
        )
    lines += [
        "",
        "## Excluded input tracks",
        "",
        "These turns remain in the inventory but do not invoke retrieval in the indicated track.",
        "",
        "| Track | Case / turn | Reason |",
        "| --- | --- | --- |",
    ]
    for item in report.exclusions:
        lines.append(f"| {item.track} | {item.case_id} / {item.turn_id} | {item.reason} |")
    selected = sorted({r.case_id for r in report.rows} | {e.case_id for e in report.exclusions})
    command = f"uv run python scripts/compare_retrieval.py --repetitions {p.repetitions}"
    if len(selected) != 24:
        command += "".join(f" --case {case}" for case in selected)
    lines += [
        "",
        "## Provenance and reproduction",
        "",
        "```bash",
        command,
        "```",
        "",
        f"- Corpus: {p.corpus_version}",
        f"- Corpus SHA-256: {p.corpus_hash}",
        f"- Fixture SHA-256: {p.fixture_sha256}",
        f"- Replay SHA-256: {p.replay_sha256}",
        f"- Resource manifest SHA-256: {p.resource_sha256}",
        f"- Git revision: {p.git_revision or 'unknown'}; "
        f"working tree dirty: {p.working_tree_dirty}",
        f"- Python: {p.python_version}; platform: {p.platform}",
        "- Provider requests: 0; model usage, monetary cost and semantic acceptance: unmeasured.",
        "",
        "| Implementation | SHA-256 |",
        "| --- | --- |",
    ]
    for name, digest in p.module_sha256.items():
        lines.append(f"| {name} | {digest} |")
    lines += [
        "",
        "## Interpretation limits",
        "",
        (
            "The fixtures already informed earlier fixes. These are descriptive "
            "regression results, not an"
        ),
        (
            "independent benchmark or evidence of broad production improvement. Unknown "
            "relevance labels"
        ),
        (
            "limit precision denominators. Supplied rewrites/scopes cannot validate "
            "actual model rewriting,"
        ),
        (
            "conversation resolution, unsupported-answer safety or factual fidelity. An "
            "embeddings decision"
        ),
        (
            "requires additional independently labeled/held-out failures and an explicit "
            "comparison feature."
        ),
        "",
    ]
    return "\n".join(lines)
