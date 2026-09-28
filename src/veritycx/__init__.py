"""Expose the maintained VerityCX package modules and single project root."""

from pathlib import Path

from veritycx import data_sources as data_sources

PROJECT_ROOT = Path(__file__).resolve().parents[2]

__all__ = ["PROJECT_ROOT", "data_sources"]
