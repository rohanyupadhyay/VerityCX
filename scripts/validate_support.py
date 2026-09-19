"""Run explicit support validation suites without claiming live or human-reviewed acceptance."""

import argparse
import json
import os
import subprocess
import sys

import httpx
from pydantic import ValidationError as SchemaError

from veritycx.policy.sources import SourceError
from veritycx.service.configuration import ConfigurationError
from veritycx.service.validation import (
    ValidationError,
    dedicated_database,
    validate_grounding,
    validate_handoff,
    validate_offline,
)


def main() -> int:
    """Select a bounded suite and return nonzero for unavailable acceptance gates."""
    parser = argparse.ArgumentParser(description="Validate durable support")
    parser.add_argument("--suite", choices=["offline", "grounding", "demo"], required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.suite != "offline" and not args.live:
        print("live_opt_in_required")
        return 1
    if args.suite == "offline" and args.live:
        print("offline_live_conflict")
        return 1
    try:
        if args.suite == "grounding":
            print(json.dumps(validate_grounding(dict(os.environ), live=args.live), sort_keys=True))
            return 1  # Human semantic review is explicitly pending.
        if args.suite == "demo":
            print(json.dumps(validate_handoff(dict(os.environ), live=True), sort_keys=True))
            return 0
        dedicated_database(os.environ.get("VERITYCX_TEST_DATABASE_URL", ""))
        # Fixed project-authored command; test processes own their own cleanup handles.
        checks = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/support", "-m", "not live", "-q", "--tb=short"],
            capture_output=True,
            check=False,
        )
        if checks.returncode:
            raise ValidationError("offline_checks_failed")
        result = validate_offline(dict(os.environ))
        handoff = validate_handoff(dict(os.environ))
        result["handoff_cases_passed"] = handoff["cases_passed"]
    except (ValidationError, SourceError, ConfigurationError) as error:
        print(str(error))
        return 1
    except (httpx.HTTPError, SchemaError):
        print("validation_failed")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
