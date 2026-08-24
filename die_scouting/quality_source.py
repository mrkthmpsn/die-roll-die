from __future__ import annotations

from typing import Protocol

import math

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

    Three families are implemented, each with its own update and its own reading of a
    `Record`: gamma with Poisson counts, where `value` is a count and `denominator` the
    opportunity it accumulated over; beta with binomial successes, where `value` is
    successes and `denominator` attempts; and normal, where `value / denominator` is a measured
    quantity per unit of denominator.
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
        """Return the two parameters of the posterior, being the prior's updated by the
        entity's observations: shape and rate for gamma, successes and failures for beta,
        mean and standard deviation for normal.

        An entity with no observations returns the prior's parameters unchanged.

        Raises:
            ValueError: if the prior's params lack a key its family needs.
        """
        observations = self.data_adapter.get_entity_observations(
            entity_id, self.stat_id, self.prior.scope
        )
        if self.prior.family == "gamma":
            self._require("alpha", "beta")
            return (
                self.prior.params["alpha"] + sum(o.value for o in observations),
                self.prior.params["beta"] + sum(o.denominator for o in observations),
            )
        if self.prior.family == "beta":
            self._require("alpha", "beta")
            return (
                self.prior.params["alpha"] + sum(o.value for o in observations),
                self.prior.params["beta"] + sum(o.denominator - o.value for o in observations),
            )
        self._require("mu", "sigma", "sigma_obs")
        mu, sigma = self.prior.params["mu"], self.prior.params["sigma"]
        observation_variance = self.prior.params["sigma_obs"] ** 2
        precision = 1.0 / sigma**2 + sum(o.denominator for o in observations) / observation_variance
        weighted = mu / sigma**2 + sum(o.value for o in observations) / observation_variance
        return weighted / precision, math.sqrt(1.0 / precision)

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws values of the entity's underlying quality from the posterior: a
        rate per unit of denominator for gamma and normal, a proportion for beta.
        """
        first, second = self.posterior_params(entity_id)
        return self._draw(first, second, n_draws).tolist()

    def sample_predictive(self, entity_id: str, n_draws: int, denominator: float) -> list[float]:
        """Draw n_draws totals the entity would record over `denominator`: a Poisson count for
        gamma, a binomial count of successes out of `denominator` attempts for beta, and a
        summed value carrying its own observation noise for normal.

        `denominator` is held fixed across the draws, so the spread reflects uncertainty about
        the entity's quality at a stated amount of opportunity.

        Raises:
            ValueError: if `denominator` is negative, or is not a whole number of attempts for
                a beta prior.
        """
        if denominator < 0:
            raise ValueError("denominator must not be negative")
        first, second = self.posterior_params(entity_id)
        draws = self._draw(first, second, n_draws)

        if self.prior.family == "gamma":
            return self.rng.poisson(draws * denominator).astype(float).tolist()
        if self.prior.family == "beta":
            if denominator != int(denominator):
                raise ValueError("a beta prior predicts over a whole number of attempts")
            return self.rng.binomial(int(denominator), draws).astype(float).tolist()
        noise = self.prior.params["sigma_obs"] * math.sqrt(denominator)
        return (draws * denominator + self.rng.normal(0.0, noise, size=n_draws)).tolist()

    def _draw(self, first: float, second: float, n_draws: int) -> np.ndarray:
        if self.prior.family == "gamma":
            return self.rng.gamma(shape=first, scale=1.0 / second, size=n_draws)
        if self.prior.family == "beta":
            return self.rng.beta(first, second, size=n_draws)
        return self.rng.normal(first, second, size=n_draws)

    def _require(self, *keys: str) -> None:
        for key in keys:
            if key not in self.prior.params:
                raise ValueError(f"a {self.prior.family} prior's params must contain {key!r}")


class BootstrapSource:
    """Produces draws by resampling the entity's own observations with replacement and
    recomputing the stat each time.
    """

    def __init__(self, data_adapter: DataAdapter, stat_id: str) -> None:
        self.data_adapter = data_adapter
        self.stat_id = stat_id

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        raise NotImplementedError
