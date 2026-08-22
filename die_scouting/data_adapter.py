from __future__ import annotations

from typing import Protocol

from .models import Record


class DataAdapter(Protocol):
    """Protocol to adapt provider-specific data to a list of Records.

    A concrete implementation might read from empty-head-data's Core API, a CSV, or
    anything else.
    """

    def get_entity_observations(
        self, entity_id: str, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-observation values for a single entity."""
        ...

    def get_population_observations(
        self, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-observation values for every entity matching `scope`."""
        ...
