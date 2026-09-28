"""Prove supported runtime entry points acquire dotenv before configuration."""

from pathlib import Path


def test_service_and_worker_call_loader_before_configuration() -> None:
    """Keep ambient loading at entry points and explicit mappings inside library APIs."""
    root = Path(__file__).resolve().parents[3]
    for relative in ("src/veritycx/service/main.py", "src/veritycx/orchestration/worker.py"):
        source = (root / relative).read_text(encoding="utf-8")
        assert source.index("load_project_environment()") < source.index("load_configuration(")

    configuration = (root / "src/veritycx/service/configuration.py").read_text(encoding="utf-8")
    assert "load_project_environment" not in configuration
