from __future__ import annotations

from typing import Protocol

from .models import Record


class DataAdapter(Protocol):
    """The only domain/provider-aware seam. Everything downstream only ever sees Records.

    A concrete implementation might read from empty-head-data's Core API, a CSV, or
    anything else — nothing above this module needs to know how observations are fetched.
    """

    def get_entity_observations(
        self, entity_id: str, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-match (or per-observation) values for a single entity."""
        ...

    def get_population_observations(
        self, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-match values across the population, for prior discovery."""
        ...
