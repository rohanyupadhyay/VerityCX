"""Define the repository-wide pytest environment-loading boundary."""

import pytest

from veritycx.environment import load_project_environment


def pytest_addoption(parser: pytest.Parser) -> None:
    """Expose an explicit escape hatch for hermetic subprocess test sessions."""
    parser.addoption(
        "--no-project-dotenv",
        action="store_true",
        help="do not load the repository-root .env for this pytest session",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Load root dotenv values unless an isolated test session explicitly opts out."""
    if not session.config.getoption("--no-project-dotenv"):
        load_project_environment()
