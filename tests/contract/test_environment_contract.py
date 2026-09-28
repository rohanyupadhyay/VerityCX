"""Validate the exact, source-derived, value-blind environment contract."""

from pathlib import Path

import pytest
from scripts.check_environment_contract import analyze_environment_contract, format_findings


def _analyze(tmp_path: Path, source: str, example: str) -> tuple[str, ...]:
    """Write one synthetic consumer and return its rendered contract findings."""
    source_path = tmp_path / "consumer.py"
    source_path.write_text(source, encoding="utf-8")
    example_path = tmp_path / ".env.example"
    example_path.write_text(example, encoding="utf-8")
    findings = analyze_environment_contract(tmp_path, (source_path,), example_path)
    return format_findings(findings)


@pytest.mark.parametrize(
    ("example", "category"),
    [
        ("", "missing:VERITYCX_DATABASE_URL"),
        ("VERITYCX_DATABASE_URL=\nEXTRA=\n", "extra:EXTRA"),
        (
            "VERITYCX_DATABASE_URL=\nVERITYCX_DATABASE_URL=\n",
            "duplicate:VERITYCX_DATABASE_URL",
        ),
        ("not an assignment\nVERITYCX_DATABASE_URL=\n", "malformed:line-1"),
        ("veritycx_database_url=\n", "wrong-case:veritycx_database_url"),
        ("export VERITYCX_DATABASE_URL=\n", "malformed:line-1"),
    ],
)
def test_strict_parser_and_exact_set(tmp_path: Path, example: str, category: str) -> None:
    """Detect every specified lexical and inventory drift category."""
    rendered = _analyze(
        tmp_path,
        'import os\nvalue = os.environ.get("VERITYCX_DATABASE_URL")\n',
        example,
    )
    assert category in rendered


def test_aliases_provider_ownership_and_external_controls(tmp_path: Path) -> None:
    """Collect literal project reads through supported aliases and omit host controls."""
    rendered = _analyze(
        tmp_path,
        """import os as operating_system
from os import getenv as read_environment
environment = operating_system.environ
database = environment["VERITYCX_DATABASE_URL"]
provider = read_environment("OPENAI_API_KEY")
home = operating_system.getenv("HOME")
""",
        "VERITYCX_DATABASE_URL=\nOPENAI_API_KEY=\n",
    )
    assert rendered == ()


def test_comments_blank_lines_and_diagnostics_are_stable(tmp_path: Path) -> None:
    """Ignore nonentries and render multiple findings in deterministic sorted order."""
    rendered = _analyze(
        tmp_path,
        'import os\nvalue = os.getenv("VERITYCX_DATABASE_URL")\n',
        "# Safe public template\n\nEXTRA_TWO=\nEXTRA_ONE=\n",
    )
    assert rendered == (
        "extra:EXTRA_ONE",
        "extra:EXTRA_TWO",
        "missing:VERITYCX_DATABASE_URL",
    )


def test_dynamic_environment_read_fails_closed(tmp_path: Path) -> None:
    """Reject dynamic name reads rather than silently omitting possible project settings."""
    rendered = _analyze(
        tmp_path,
        'import os\nname = "VERITYCX_DATABASE_URL"\nvalue = os.getenv(name)\n',
        "",
    )
    assert any(item.startswith("dynamic:") for item in rendered)


@pytest.mark.parametrize(
    "unsafe",
    [
        "postgresql://user:password@localhost/database",
        "/home/alice/private/key.json",
        "sk-live-secret-canary",
    ],
)
def test_unsafe_values_are_rejected_without_disclosure(tmp_path: Path, unsafe: str) -> None:
    """Report only the affected name when a placeholder could be a usable secret."""
    rendered = _analyze(
        tmp_path,
        'import os\nvalue = os.getenv("OPENAI_API_KEY")\n',
        f"OPENAI_API_KEY={unsafe}\n",
    )
    assert "unsafe-placeholder:OPENAI_API_KEY" in rendered
    assert unsafe not in "\n".join(rendered)


def test_absent_template_is_value_blind(tmp_path: Path) -> None:
    """Describe a missing contract file without inspecting a local dotenv file."""
    canary = "never-print-this-canary"
    source_path = tmp_path / "consumer.py"
    source_path.write_text('import os\nvalue = os.getenv("OPENAI_API_KEY")\n', encoding="utf-8")
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={canary}\n", encoding="utf-8")
    rendered = format_findings(
        analyze_environment_contract(tmp_path, (source_path,), tmp_path / ".env.example")
    )
    assert rendered == ("missing-template:.env.example",)
    assert canary not in "\n".join(rendered)


def test_live_repository_inventory_is_exact() -> None:
    """Keep the checked-in template synchronized with every maintained consumer."""
    root = Path(__file__).resolve().parents[2]
    source_paths = tuple(
        sorted(
            path
            for scope in (root / "src", root / "scripts", root / "tests")
            for path in scope.rglob("*.py")
            if path.name != "check_environment_contract.py"
        )
    )
    findings = analyze_environment_contract(root, source_paths, root / ".env.example")
    assert format_findings(findings) == ()
