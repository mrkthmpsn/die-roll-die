from __future__ import annotations

from typing import Protocol

from .data_adapter import DataAdapter
from .models import PriorParams


class QualitySource(Protocol):
    """Protocol for producing draws of an entity's quality."""

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws plausible values of this entity's true quality."""
        ...


class AnalyticSource:
    """Produces draws from a closed-form posterior, by conjugate update of `prior` with
    the entity's own observations. The update rule follows the prior's family, e.g.
    Beta-Binomial or Normal-Normal.
    """

    def __init__(self, prior: PriorParams, data_adapter: DataAdapter, stat_id: str) -> None:
        self.prior = prior
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError


class BootstrapSource:
    """Produces draws by resampling the entity's own observations with replacement and
    recomputing the stat each time.
    """

    def __init__(self, data_adapter: DataAdapter, stat_id: str) -> None:
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError
