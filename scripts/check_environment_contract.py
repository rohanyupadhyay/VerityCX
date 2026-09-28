"""Check that maintained environment reads exactly match the safe root template."""

from __future__ import annotations

import argparse
import ast
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from veritycx import PROJECT_ROOT

_PROJECT_PROVIDER_NAMES = frozenset({"OPENAI_API_KEY", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"})
_ASSIGNMENT = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)")
_OBVIOUS_PLACEHOLDERS = frozenset(
    {"changeme", "example", "placeholder", "replace-me", "replace_me", "your-value", "your_value"}
)


@dataclass(frozen=True, order=True)
class Finding:
    """Describe one deterministic, value-free contract problem."""

    category: str
    name: str


@dataclass(frozen=True)
class EnvironmentRead:
    """Record one literal project setting read or one unsupported dynamic read."""

    name: str | None
    location: str


class _EnvironmentReadVisitor(ast.NodeVisitor):
    """Collect environment reads while tracking common aliases within one Python module."""

    def __init__(self, project_root: Path, source_path: Path) -> None:
        """Initialize source-relative evidence and standard-library alias sets."""
        try:
            self._display_path = source_path.relative_to(project_root).as_posix()
        except ValueError:
            self._display_path = source_path.name
        self.os_aliases: set[str] = {"os"}
        self.getenv_aliases: set[str] = set()
        self.environ_aliases: set[str] = set()
        self.reads: list[EnvironmentRead] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Track aliases introduced by ``import os`` statements."""
        for alias in node.names:
            if alias.name == "os":
                self.os_aliases.add(alias.asname or alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track direct aliases for ``os.getenv`` and ``os.environ``."""
        if node.module == "os":
            for alias in node.names:
                local = alias.asname or alias.name
                if alias.name == "getenv":
                    self.getenv_aliases.add(local)
                elif alias.name == "environ":
                    self.environ_aliases.add(local)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track simple local aliases of the process environment mapping."""
        if self._is_environ(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.environ_aliases.add(target.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Collect ``getenv`` and environment-mapping ``get`` calls."""
        is_read = False
        if isinstance(node.func, ast.Name) and node.func.id in self.getenv_aliases:
            is_read = True
        elif isinstance(node.func, ast.Attribute):
            if (
                node.func.attr == "getenv"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in self.os_aliases
            ):
                is_read = True
            elif node.func.attr == "get" and self._is_environ(node.func.value):
                is_read = True
            elif (
                node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and _is_project_owned(node.args[0].value)
            ):
                # Explicit Mapping interfaces are intentionally isolated from dotenv loading,
                # but their literal project keys still define the repository contract.
                is_read = True
        if is_read:
            self._record_argument(node.args[0] if node.args else None, node.lineno)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Collect direct subscripting of the process environment mapping."""
        if self._is_environ(node.value):
            self._record_argument(node.slice, node.lineno)
        self.generic_visit(node)

    def _is_environ(self, node: ast.expr) -> bool:
        """Return whether an expression names ``os.environ`` or a tracked alias."""
        if isinstance(node, ast.Name):
            return node.id in self.environ_aliases
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and isinstance(node.value, ast.Name)
            and node.value.id in self.os_aliases
        )

    def _record_argument(self, node: ast.expr | None, line: int) -> None:
        """Record a literal name or a safe source location for a dynamic read."""
        name = (
            node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
        )
        self.reads.append(EnvironmentRead(name, f"{self._display_path}:{line}"))


def _collect_reads(project_root: Path, source_paths: Iterable[Path]) -> tuple[EnvironmentRead, ...]:
    """Parse maintained sources and return stable environment-read evidence."""
    reads: list[EnvironmentRead] = []
    for path in sorted(source_paths):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            try:
                display = path.relative_to(project_root).as_posix()
            except ValueError:
                display = path.name
            reads.append(EnvironmentRead(None, f"{display}:parse"))
            continue
        visitor = _EnvironmentReadVisitor(project_root, path)
        visitor.visit(tree)
        reads.extend(visitor.reads)
    return tuple(reads)


def _is_project_owned(name: str) -> bool:
    """Apply the documented VerityCX-prefix and adopted-provider ownership policy."""
    return name.startswith("VERITYCX_") or name in _PROJECT_PROVIDER_NAMES


def _is_safe_placeholder(value: str) -> bool:
    """Accept only empty or unmistakably synthetic template values."""
    normalized = value.strip().strip("\"'")
    if not normalized:
        return True
    lowered = normalized.lower()
    return lowered in _OBVIOUS_PLACEHOLDERS or (
        normalized.startswith("<") and normalized.endswith(">") and len(normalized) > 2
    )


def _parse_example(path: Path, required: frozenset[str]) -> tuple[list[str], list[Finding]]:
    """Parse strict assignments without returning or reporting their values."""
    names: list[str] = []
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names, [Finding("missing-template", path.name)]
    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        if match is None or line.startswith("export "):
            findings.append(Finding("malformed", f"line-{number}"))
            continue
        name = match.group("name")
        names.append(name)
        if name not in required and name.upper() in required:
            findings.append(Finding("wrong-case", name))
        if not _is_safe_placeholder(match.group("value")):
            findings.append(Finding("unsafe-placeholder", name))
    return names, findings


def analyze_environment_contract(
    project_root: Path, source_paths: Sequence[Path], example_path: Path
) -> tuple[Finding, ...]:
    """Compare source-derived project names with a strict, safe example template."""
    findings: list[Finding] = []
    required_names: set[str] = set()
    for read in _collect_reads(project_root, source_paths):
        if read.name is None:
            findings.append(Finding("dynamic", read.location))
        elif _is_project_owned(read.name):
            required_names.add(read.name)
    required = frozenset(required_names)
    example_names, parse_findings = _parse_example(example_path, required)
    findings.extend(parse_findings)
    if any(item.category == "missing-template" for item in findings):
        return tuple(sorted(set(findings)))
    counts = Counter(example_names)
    findings.extend(Finding("duplicate", name) for name, count in counts.items() if count > 1)
    example_set = frozenset(example_names)
    findings.extend(Finding("missing", name) for name in required - example_set)
    findings.extend(Finding("extra", name) for name in example_set - required)
    return tuple(sorted(set(findings)))


def format_findings(findings: Iterable[Finding]) -> tuple[str, ...]:
    """Render findings as sorted category-and-name diagnostics without values."""
    return tuple(f"{finding.category}:{finding.name}" for finding in sorted(findings))


def _repository_sources() -> tuple[Path, ...]:
    """Return maintained Python consumers in the documented repository scopes."""
    checker = Path(__file__).resolve()
    return tuple(
        sorted(
            path
            for scope in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts", PROJECT_ROOT / "tests")
            for path in scope.rglob("*.py")
            if path.resolve() != checker
        )
    )


def main() -> int:
    """Print one success line or sorted name-only findings and return a stable status."""
    parser = argparse.ArgumentParser(description="Check the root environment-name contract")
    parser.parse_args()
    findings = analyze_environment_contract(
        PROJECT_ROOT, _repository_sources(), PROJECT_ROOT / ".env.example"
    )
    if findings:
        for line in format_findings(findings):
            print(line)
        return 1
    print("environment_contract_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
