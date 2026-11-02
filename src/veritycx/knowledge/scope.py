"""Describe bounded untrusted search scope without granting factual authority."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field, field_validator, model_validator

from veritycx.conversations.models import ClosedModel
from veritycx.knowledge.catalog import CATEGORIES, CategoryKey

if TYPE_CHECKING:
    from veritycx.knowledge.models import CatalogEntry

OVERVIEW_SCOPE_NOTE = (
    "These products or services are documented in the approved policies; "
    "this may not be a complete list of offerings."
)


class SearchScope(ClosedModel):
    """Constrain model-selected discovery scope to known canonical category keys."""

    scope: Literal["focused", "category_overview"]
    categories: tuple[CategoryKey, ...] = Field(max_length=6)

    @field_validator("categories")
    @classmethod
    def canonical_categories(cls, value: tuple[CategoryKey, ...]) -> tuple[CategoryKey, ...]:
        """Reject duplicates and use server-owned category order."""
        if len(set(value)) != len(value):
            raise ValueError("duplicate_categories")
        return tuple(key for key in CATEGORIES if key in value)

    @model_validator(mode="after")
    def consistent_scope(self) -> SearchScope:
        """Focused retrieval has no category expansion; overviews must name categories."""
        if (self.scope == "category_overview") != bool(self.categories):
            raise ValueError("invalid_search_scope")
        return self


class CategoryHint(ClosedModel):
    """Supply a server-owned label for a category represented in approved sources."""

    key: CategoryKey
    label: str

    @model_validator(mode="after")
    def canonical_label(self) -> CategoryHint:
        """Reject labels that disagree with the shared category policy."""
        if self.label != CATEGORIES[self.key]:
            raise ValueError("invalid_category_label")
        return self


def category_hints(catalog_index: Sequence[CatalogEntry]) -> tuple[CategoryHint, ...]:
    """List nonempty categories without implying a complete offering catalogue."""
    present = {entry.category for entry in catalog_index}
    return tuple(
        CategoryHint(key=key, label=label) for key, label in CATEGORIES.items() if key in present
    )


class CategoryCoverage(ClosedModel):
    """Measure source-document coverage rather than real-world product completeness."""

    eligible_document_count: int = Field(ge=0)
    represented_document_count: int = Field(ge=0)
    coverage_truncated: bool

    @model_validator(mode="after")
    def consistent_counts(self) -> CategoryCoverage:
        """Require honest counts and an exact omission flag."""
        if (
            self.represented_document_count > self.eligible_document_count
            or self.coverage_truncated
            != (self.represented_document_count < self.eligible_document_count)
        ):
            raise ValueError("invalid_category_coverage")
        return self


class SearchContext(ClosedModel):
    """Keep category scope and observed coverage separate from selected policy facts."""

    search_scope: SearchScope
    coverage: CategoryCoverage | None

    @model_validator(mode="after")
    def consistent_coverage(self) -> SearchContext:
        """Coverage is meaningful only for a category overview."""
        if (self.search_scope.scope == "category_overview") != (self.coverage is not None):
            raise ValueError("invalid_search_coverage")
        return self
