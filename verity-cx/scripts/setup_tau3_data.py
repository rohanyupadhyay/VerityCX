"""Expose the project-root tau3 acquisition and read-only validation command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from veritycx.data_sources.tau3 import (
    SetupResult,
    Tau3Config,
    Tau3OperationError,
    format_tau3_diagnostic,
    setup_tau3_data,
)


def _parser() -> argparse.ArgumentParser:
    """Build the closed setup command-line parser.

    Returns:
        Parser exposing only help and the read-only `--check` mode.
    """
    parser = argparse.ArgumentParser(
        description="Acquire or validate the pinned tau3-Banking checkout.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate an existing checkout without creating or changing state",
    )
    return parser


def _format_success(result: SetupResult) -> str:
    """Format one deterministic non-sensitive setup success summary.

    Args:
        result: Verified setup result returned by the reusable module.

    Returns:
        Stable line-oriented human-readable output.
    """
    return "\n".join(
        (
            f"status: {result.status}",
            f"mode: {result.mode}",
            f"checkout: {result.checkout}",
            f"tag: {result.tag}",
            f"commit: {result.commit_sha}",
        ),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path | None = None,
    config: Tau3Config | None = None,
) -> int:
    """Run setup and translate expected outcomes into the public CLI contract.

    Args:
        argv: Optional arguments for testing; production uses process arguments.
        project_root: Optional explicit test root; production derives from this script.
        config: Optional typed test injection; production loads fixed configuration.

    Returns:
        Zero for success or one for an expected operational failure.
    """
    arguments = _parser().parse_args(argv)
    root = project_root if project_root is not None else Path(__file__).resolve().parents[1]
    try:
        result = setup_tau3_data(root, config=config, check_only=bool(arguments.check))
    except Tau3OperationError as error:
        print(format_tau3_diagnostic(error), file=sys.stderr)
        return 1
    print(_format_success(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
