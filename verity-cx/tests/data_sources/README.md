<!-- Documents the network-independent data-source verification module. -->

# Data-Source Tests

## Purpose and Boundaries

`test_tau3.py` verifies configuration, Git, filesystem, setup, inspection, CLI, transaction,
preservation, and non-disclosure behavior. Tests never acquire the official repository or use real
upstream content. They create temporary local working and bare Git repositories plus runtime-only
synthetic documents, JSON, tasks, and unique disclosure canaries.

## Test Design

Fixtures independently derive the local origin and commit, then exercise first install, offline
existing/check modes, invalid provenance, dirty state, malformed or incomplete data, owned cleanup,
foreign state preservation, destination races, and two-observation inspection. Tree snapshots compare
file bytes, object/link kind, exposed mode bits, and link targets while intentionally excluding access
timestamps. Assertions treat untrusted filenames as opaque and prohibit document, record, task,
answer, reference-action, and grading canaries in results, errors, representations, serialization,
stdout, and stderr.

POSIX link and Windows junction/reparse behavior is capability-aware. Permission failures are injected
through typed file operations so Windows and POSIX exercise the same safety assertion without relying
on account privilege. Platform-native path failures must terminate safely; skips are permitted only
when a primitive cannot be created and never replace shared mocked reparse coverage.

## Dependencies, Usage, and Failures

The suite requires Python 3.12, pytest, and Git 2.34 or newer. It is network-independent and safe to
run from any current directory through the explicit test project roots.

```text
uv run pytest tests/data_sources/test_tau3.py
uv run pytest tests/data_sources/test_tau3.py -k first_install --durations=1
```

A failure indicates a contract regression or an unavailable declared prerequisite. Generated
temporary repositories are pytest-owned and are not production configuration or acquisition state.
