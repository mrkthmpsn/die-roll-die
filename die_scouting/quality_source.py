from __future__ import annotations

from typing import Protocol

import numpy as np

from .data_adapter import DataAdapter
from .models import PriorParams


class QualitySource(Protocol):
    """Protocol for producing draws of an entity's quality."""

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws plausible values of this entity's true quality."""
        ...


class AnalyticSource:
    """Produces draws from a closed-form posterior, by conjugate update of `prior` with
    the entity's own observations.

    The gamma family is implemented as a Gamma-Poisson update, where each observation's
    `value` is a count and its `exposure` the amount of opportunity that count accumulated
    over.
    """

    def __init__(
        self,
        prior: PriorParams,
        data_adapter: DataAdapter,
        stat_id: str,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.prior = prior
        self.data_adapter = data_adapter
        self.stat_id = stat_id
        self.rng = np.random.default_rng() if rng is None else rng

    def posterior_params(self, entity_id: str) -> tuple[float, float]:
        """Return the posterior's shape and rate, being the prior's `alpha` and `beta`
        updated by the summed values and summed exposures of the entity's observations.

        An entity with no observations returns the prior's parameters unchanged.

        Raises:
            NotImplementedError: if the prior's family is anything other than "gamma".
            ValueError: if the prior's params lack an "alpha" or "beta" key.
        """
        if self.prior.family != "gamma":
            raise NotImplementedError(
                f"conjugate update for family {self.prior.family!r} is not implemented"
            )
        for key in ("alpha", "beta"):
            if key not in self.prior.params:
                raise ValueError(f"gamma prior params must contain {key!r}")

        observations = self.data_adapter.get_entity_observations(
            entity_id, self.stat_id, self.prior.scope
        )
        alpha = self.prior.params["alpha"] + sum(o.value for o in observations)
        beta = self.prior.params["beta"] + sum(o.exposure for o in observations)
        return alpha, beta

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws values of the entity's rate from the posterior, in the units the
        prior's exposure is measured in.
        """
        alpha, beta = self.posterior_params(entity_id)
        return self._draw_rates(alpha, beta, n_draws).tolist()

    def sample_predictive(self, entity_id: str, n_draws: int, exposure: float) -> list[float]:
        """Draw n_draws counts the entity would record over `exposure`, each a Poisson
        draw at a rate itself drawn from the posterior.

        Values are whole numbers held as floats. `exposure` is held fixed across the draws,
        so the spread reflects uncertainty about the rate at a stated amount of opportunity.

        Raises:
            ValueError: if `exposure` is negative.
        """
        if exposure < 0:
            raise ValueError("exposure must not be negative")
        alpha, beta = self.posterior_params(entity_id)
        rates = self._draw_rates(alpha, beta, n_draws)
        return self.rng.poisson(rates * exposure).astype(float).tolist()

    def _draw_rates(self, alpha: float, beta: float, n_draws: int) -> np.ndarray:
        return self.rng.gamma(shape=alpha, scale=1.0 / beta, size=n_draws)


class BootstrapSource:
    """Produces draws by resampling the entity's own observations with replacement and
    recomputing the stat each time.
    """

    def __init__(self, data_adapter: DataAdapter, stat_id: str) -> None:
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError
