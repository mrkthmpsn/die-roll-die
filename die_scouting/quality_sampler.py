from __future__ import annotations

from typing import Protocol

import math

import numpy as np

from .data_adapter import DataAdapter
from .models import POSTERIOR_PARAM_NAMES, PriorParams


class QualitySampler(Protocol):
    """Protocol for producing draws of an entity's quality."""

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws plausible values of this entity's true quality."""
        ...


class PosteriorSampler:
    """Produces draws from a closed-form posterior, by conjugate update of `prior` with
    the entity's own observations.

    Four models are implemented, each reading a `Record` its own way:

    - `gamma_poisson`: `value` is a count of events and `denominator` the exposure they
      occurred in.
    - `gamma_exponential`: `value` is an amount of time and `denominator` the number of
      events that filled it — the same two quantities as `gamma_poisson`, in the opposite
      fields, because there the time was fixed and here the events are.
    - `beta_binomial`: `value` is a count of successes and `denominator` a count of
      attempts.
    - `normal_normal`: `value / denominator` is a measured quantity per unit of denominator.
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
        entity's observations: shape and rate for the two gamma models, successes and
        failures for beta_binomial, mean and standard deviation for normal_normal.

        Both gamma models add the number of events to `alpha` and the amount of time to
        `beta`; they differ only in which `Record` field holds which, `gamma_poisson`
        counting events over a fixed time and `gamma_exponential` timing a fixed number of
        events.

        The two are named by `POSTERIOR_PARAM_NAMES` under the prior's model.

        An entity with no observations returns the prior's parameters unchanged.

        Raises:
            ValueError: if the entity's observations are of a different entity type than
                the prior describes, or if the prior's params lack a key its model needs.
        """
        observations = self.data_adapter.get_entity_observations(
            entity_id, self.stat_id, self.prior.scope
        )
        for observation in observations:
            if observation.entity_type != self.prior.entity_type:
                raise ValueError(
                    f"entity {entity_id!r} is a {observation.entity_type!r} and the prior "
                    f"describes a {self.prior.entity_type!r}"
                )
        if self.prior.model == "gamma_poisson":
            self._require(*POSTERIOR_PARAM_NAMES[self.prior.model])
            return (
                self.prior.params["alpha"] + sum(o.value for o in observations),
                self.prior.params["beta"] + sum(o.denominator for o in observations),
            )
        if self.prior.model == "gamma_exponential":
            self._require(*POSTERIOR_PARAM_NAMES[self.prior.model])
            return (
                self.prior.params["alpha"] + sum(o.denominator for o in observations),
                self.prior.params["beta"] + sum(o.value for o in observations),
            )
        if self.prior.model == "beta_binomial":
            self._require(*POSTERIOR_PARAM_NAMES[self.prior.model])
            return (
                self.prior.params["alpha"] + sum(o.value for o in observations),
                self.prior.params["beta"] + sum(o.denominator - o.value for o in observations),
            )
        self._require(*POSTERIOR_PARAM_NAMES["normal_normal"], "sigma_obs")
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
        """Draw n_draws totals the entity would record over `denominator`, which the model
        decides the meaning of: an amount of exposure for `gamma_poisson`, giving a Poisson
        count; a number of attempts for `beta_binomial`, giving a count of successes; a
        number of events for `gamma_exponential`, giving the total time they take; and a
        number of periods for `normal_normal`, giving a summed value.

        `denominator` is held fixed across the draws, so the spread reflects uncertainty about
        the entity's quality at a stated amount of opportunity.

        Raises:
            ValueError: if `denominator` is negative, or is not a whole number where the
                model counts it — attempts for `beta_binomial`, events for
                `gamma_exponential`.
        """
        if denominator < 0:
            raise ValueError("denominator must not be negative")
        first, second = self.posterior_params(entity_id)
        draws = self._draw(first, second, n_draws)

        if self.prior.model == "gamma_poisson":
            return self.rng.poisson(draws * denominator).astype(float).tolist()
        if self.prior.model == "gamma_exponential":
            if denominator != int(denominator):
                raise ValueError(
                    "a gamma_exponential prior predicts over a whole number of events"
                )
            return self.rng.gamma(shape=denominator, scale=1.0 / draws).tolist()
        if self.prior.model == "beta_binomial":
            if denominator != int(denominator):
                raise ValueError("a beta prior predicts over a whole number of attempts")
            return self.rng.binomial(int(denominator), draws).astype(float).tolist()
        noise = self.prior.params["sigma_obs"] * math.sqrt(denominator)
        return (draws * denominator + self.rng.normal(0.0, noise, size=n_draws)).tolist()

    def _draw(self, first: float, second: float, n_draws: int) -> np.ndarray:
        if self.prior.model in ("gamma_poisson", "gamma_exponential"):
            return self.rng.gamma(shape=first, scale=1.0 / second, size=n_draws)
        if self.prior.model == "beta_binomial":
            return self.rng.beta(first, second, size=n_draws)
        return self.rng.normal(first, second, size=n_draws)

    def _require(self, *keys: str) -> None:
        for key in keys:
            if key not in self.prior.params:
                raise ValueError(f"a {self.prior.model} prior's params must contain {key!r}")


class BootstrapSampler:
    """Produces draws by case resampling the entity's own observations: whole records
    drawn with replacement, so a value keeps the denominator it was measured against.

    One draw is the sum of the drawn values divided by the sum of their denominators, so a
    draw can only fall between the lowest and highest rate any single observation carries.
    """

    def __init__(
        self,
        data_adapter: DataAdapter,
        stat_id: str,
        scope: dict[str, str] | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.data_adapter = data_adapter
        self.stat_id = stat_id
        self.scope = scope
        self.rng = np.random.default_rng() if rng is None else rng

    def sample(self, entity_id: str, n_draws: int) -> list[float]:
        """Draw n_draws values of the entity's rate, each the ratio of summed values to
        summed denominators over one resample of its observations.

        Raises:
            ValueError: if the entity has fewer than two observations, one observation
                resampling only to itself, or if any denominator is not positive.
        """
        observations = self.data_adapter.get_entity_observations(
            entity_id, self.stat_id, self.scope
        )
        if len(observations) < 2:
            raise ValueError(
                f"entity {entity_id!r} has {len(observations)} observations and resampling "
                f"needs at least 2"
            )
        values = np.array([o.value for o in observations], dtype=float)
        denominators = np.array([o.denominator for o in observations], dtype=float)
        if not np.all(denominators > 0):
            raise ValueError(f"entity {entity_id!r} has an observation with a denominator of 0")

        picks = self.rng.integers(0, len(observations), size=(n_draws, len(observations)))
        return (values[picks].sum(axis=1) / denominators[picks].sum(axis=1)).tolist()
