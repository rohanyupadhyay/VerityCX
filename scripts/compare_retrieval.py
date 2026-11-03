"""Compare retained retrieval versions offline without models, storage or corpus activation."""

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from veritycx.service.retrieval_comparison import compare_retrieval
from veritycx.service.retrieval_comparison_report import render_markdown


class _SafeParser(argparse.ArgumentParser):
    """Keep malformed CLI content out of captured logs while preserving --help."""

    def error(self, message: str) -> NoReturn:
        """Recognize only our finite repetition error; never reflect arbitrary input."""
        category = (
            "invalid_comparison_repetitions"
            if message == "argument --repetitions: invalid_comparison_repetitions"
            else "invalid_comparison_arguments"
        )
        self.exit(2, category + "\n")


def _repetitions(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid_comparison_repetitions") from None
    if not 1 <= count <= 20:
        raise argparse.ArgumentTypeError("invalid_comparison_repetitions")
    return count


def main(arguments: Sequence[str] | None = None) -> int:
    """Print a content-free structured report; Markdown requires an explicit new destination."""
    parser = _SafeParser(description="Offline frozen retrieval component comparison")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--repetitions", type=_repetitions, default=5)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(arguments)
    try:
        if args.markdown and (args.markdown.exists() or args.markdown.is_symlink()):
            print("comparison_report_exists")
            return 1
        report = compare_retrieval(case_ids=args.case_ids, repetitions=args.repetitions)
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            with args.markdown.open("x", encoding="utf-8") as output:
                output.write(render_markdown(report))
        print(report.model_dump_json())
        return 0 if report.passed else 1
    except Exception as error:
        known = {
            "invalid_regression_selection",
            "invalid_regression_cases",
            "invalid_regression_replays",
            "invalid_regression_source",
            "invalid_comparison_repetitions",
            "comparison_inputs_changed",
        }
        category = str(error)
        print(category if category in known else "retrieval_comparison_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
