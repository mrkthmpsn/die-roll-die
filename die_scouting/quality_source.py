from __future__ import annotations

from typing import Protocol

from .data_adapter import DataAdapter
from .models import PriorParams


class QualitySource(Protocol):
    """Uniform sampling interface. Implementations differ in mechanism, never in contract."""

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws plausible values of this entity's true quality."""
        ...


class AnalyticSource:
    """Closed-form posterior: conjugate update of a discovered prior with the entity's
    own observations (e.g. Beta-Binomial, Normal-Normal — depends on the prior's family).
    """

    def __init__(self, prior: PriorParams, data_adapter: DataAdapter, stat_id: str) -> None:
        self.prior = prior
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError


class BootstrapSource:
    """Resamples the entity's own observations with replacement and recomputes a stat
    function each time. No named distribution family required.
    """

    def __init__(self, data_adapter: DataAdapter, stat_id: str) -> None:
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError
