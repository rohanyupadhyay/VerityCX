"""Expose the project-root, validation-first tau3 banking inspection command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from veritycx.data_sources.tau3 import (
    InspectionSummary,
    Tau3Config,
    Tau3OperationError,
    inspect_tau3_data,
)


def _parser() -> argparse.ArgumentParser:
    """Build the closed, no-option inspection command-line parser."""
    return argparse.ArgumentParser(
        description="Inspect safe metadata from the pinned tau3-Banking checkout.",
    )


def _format_summary(summary: InspectionSummary) -> str:
    """Format an approved summary as deterministic line-oriented text.

    Args:
        summary: Fully validated immutable inspection result.

    Returns:
        Buffered output containing only contract-approved aggregate fields.
    """
    lines = [
        f"tag: {summary.tag}",
        f"commit: {summary.commit_sha}",
        f"documents: {summary.document_count}",
        f"tasks: {summary.task_count}",
        "database:",
    ]
    for shape in summary.database_collections:
        suffix = f", count={shape.direct_count}" if shape.direct_count is not None else ""
        lines.append(f"  {shape.name}: kind={shape.json_kind}{suffix}")
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path | None = None,
    config: Tau3Config | None = None,
) -> int:
    """Inspect banking metadata and translate expected failures to exit code one.

    Args:
        argv: Optional arguments for testing; production uses process arguments.
        project_root: Optional explicit test root; production derives from this script.
        config: Optional typed test injection; production loads fixed configuration.

    Returns:
        Zero for success or one for an expected operational failure.
    """
    _parser().parse_args(argv)
    root = project_root if project_root is not None else Path(__file__).resolve().parents[1]
    try:
        summary = inspect_tau3_data(root, config=config)
    except Tau3OperationError as error:
        print(f"error[{error.category}]: {error.message}", file=sys.stderr)
        return 1
    print(_format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
