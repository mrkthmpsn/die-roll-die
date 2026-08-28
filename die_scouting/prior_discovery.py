from __future__ import annotations

import math
import statistics
from typing import Literal

from .errors import InsufficientData, UnsuitableFamily
from .models import PriorParams, Record

MIN_DENOMINATOR = 10.0


def fit_prior(
    observations: list[Record],
    family: Literal["beta", "gamma", "normal"],
    stat_id: str,
    scope: dict[str, str] | None = None,
    min_denominator: float = MIN_DENOMINATOR,
) -> PriorParams:
    """Fit prior parameters for a stat from population-wide observations, by method of
    moments against `family`.

    `family` is supplied by the caller: it states which values the stat can take at all,
    which no sample establishes, since an unobserved value and an impossible one look
    alike in data.

    The prior's `entity_type` is read off the observations rather than passed, so it cannot
    disagree with the data it was fitted from.

    Observations with a denominator below `min_denominator` are excluded from the fit, their
    rates being dominated by the small denominator.

    Output is intended to be persisted via a `PriorStore` and re-read, not recomputed
    per call.

    Raises:
        ValueError: if `observations` is empty, or holds more than one entity type.
        InsufficientData: if there are too few observations to fit `family`.
        UnsuitableFamily: if the observations contradict `family`.
    """
    entity_types = {o.entity_type for o in observations}
    if not entity_types:
        raise ValueError(f"no observations of {stat_id!r} to fit a prior from")
    if len(entity_types) > 1:
        raise ValueError(
            f"observations of {stat_id!r} hold more than one entity type "
            f"({', '.join(sorted(entity_types))}); a prior describes one kind of entity"
        )
    fit = {"beta": _fit_beta, "gamma": _fit_gamma, "normal": _fit_normal}[family]
    return PriorParams(
        stat_id=stat_id,
        entity_type=entity_types.pop(),
        scope=scope or {},
        family=family,
        params=fit(observations, min_denominator),
    )


def _usable(observations: list[Record], min_denominator: float, family: str) -> list[Record]:
    """Return the observations whose denominator reaches `min_denominator`.

    Raises:
        InsufficientData: if fewer than two do.
    """
    usable = [o for o in observations if o.denominator >= min_denominator]
    if len(usable) < 2:
        raise InsufficientData(
            f"fitting a {family} prior needs at least two observations of denominator "
            f"{min_denominator} or more; got {len(usable)}"
        )
    return usable


def _corrected_variance(observed: float, noise: float) -> float:
    """Return `observed` less `noise`, falling back to `observed` where the subtraction is
    not positive, which gives a wider prior.

    Raises:
        InsufficientData: if `observed` is not positive either.
    """
    variance = observed - noise
    if variance <= 0:
        variance = observed
    if variance <= 0:
        raise InsufficientData(
            "the observations' rates are all equal, so there is no spread to estimate"
        )
    return variance


def _fit_gamma(observations: list[Record], min_denominator: float) -> dict[str, float]:
    """Return `alpha` and `beta` for a gamma over the observations' rates, matched to the
    rates' mean and to their variance less the variance a Poisson count contributes.

    A rate `value / denominator` varies both with the spread of true rates and with the
    randomness of the count itself, the latter contributing `mean / denominator`. Subtracting
    its average across the observations leaves the spread the prior should carry; where
    the subtraction is not positive, the uncorrected variance is used, giving a wider
    prior.

    Raises:
        InsufficientData: if fewer than two observations reach `min_denominator`, or if
            their rates have a mean or a variance of zero.
    """
    usable = _usable(observations, min_denominator, "gamma")

    rates = [o.value / o.denominator for o in usable]
    mean = statistics.fmean(rates)
    if mean <= 0:
        raise InsufficientData(
            "every observation's value is zero, so there is no rate to estimate"
        )

    poisson_variance = mean * statistics.fmean(1.0 / o.denominator for o in usable)
    variance = _corrected_variance(statistics.variance(rates), poisson_variance)

    return {"alpha": mean**2 / variance, "beta": mean / variance}


def _fit_beta(observations: list[Record], min_denominator: float) -> dict[str, float]:
    """Return `alpha` and `beta` for a beta over the observations' proportions, where
    `value` is a count of successes and `denominator` the attempts they came from.

    A proportion observed over `n` attempts carries binomial noise of `p * (1 - p) / n` on
    top of the spread of true proportions; subtracting its average across the observations
    leaves the spread the prior should carry, and where the subtraction is not positive the
    uncorrected variance is used.

    Raises:
        InsufficientData: if fewer than two observations reach `min_denominator`, or if
            their mean proportion is 0 or 1.
        UnsuitableFamily: if any observation's value is negative or exceeds its
            denominator, or if their spread exceeds what a beta with that mean can produce.
    """
    for o in observations:
        if o.value < 0 or o.value > o.denominator:
            raise UnsuitableFamily(
                f"entity {o.entity_id!r} has value {o.value} against denominator {o.denominator}; "
                "a beta prior needs successes counted out of attempts"
            )

    usable = _usable(observations, min_denominator, "beta")

    proportions = [o.value / o.denominator for o in usable]
    mean = statistics.fmean(proportions)
    if not 0 < mean < 1:
        raise InsufficientData(
            f"every observation's proportion is {mean:.0f}, so there is no proportion to "
            "estimate"
        )

    binomial_variance = mean * (1 - mean) * statistics.fmean(1.0 / o.denominator for o in usable)
    variance = _corrected_variance(statistics.variance(proportions), binomial_variance)

    concentration = mean * (1 - mean) / variance - 1
    if concentration <= 0:
        raise UnsuitableFamily(
            "the observations' proportions are more spread than any beta with their mean"
        )

    return {"alpha": mean * concentration, "beta": (1 - mean) * concentration}


def _fit_normal(observations: list[Record], min_denominator: float) -> dict[str, float]:
    """Return `mu`, `sigma` and `sigma_obs` for a normal over the observations' rates,
    where `sigma` is the spread of rates between entities and `sigma_obs` the spread of one
    entity's rates around its own mean, per unit of denominator.

    `sigma_obs` is estimated by pooling the within-entity spread across every entity with
    two or more observations, weighting each observation by its denominator; a normal's spread
    is not implied by its mean, unlike a Poisson's or a binomial's, so it has to be measured
    from entities that appear more than once.

    Raises:
        InsufficientData: if fewer than two observations reach `min_denominator`, if no
            entity has two or more of them, if every repeated observation is identical, or
            if the rates have no spread.
    """
    usable = _usable(observations, min_denominator, "normal")

    by_entity: dict[str, list[Record]] = {}
    for o in usable:
        by_entity.setdefault(o.entity_id, []).append(o)

    weighted_squares = 0.0
    degrees_of_freedom = 0
    for records in by_entity.values():
        if len(records) < 2:
            continue
        denominator = sum(r.denominator for r in records)
        entity_mean = sum(r.value for r in records) / denominator
        weighted_squares += sum(r.denominator * (r.value / r.denominator - entity_mean) ** 2 for r in records)
        degrees_of_freedom += len(records) - 1

    if degrees_of_freedom == 0:
        raise InsufficientData(
            "fitting a normal prior needs at least one entity with two or more "
            "observations, to estimate how much one entity's values vary around its own mean"
        )
    observation_variance = weighted_squares / degrees_of_freedom
    if observation_variance <= 0:
        raise InsufficientData(
            "every entity's repeated observations are identical, so there is no spread to "
            "estimate"
        )

    rates = [o.value / o.denominator for o in usable]
    mean = statistics.fmean(rates)
    noise = observation_variance * statistics.fmean(1.0 / o.denominator for o in usable)
    variance = _corrected_variance(statistics.variance(rates), noise)

    return {
        "mu": mean,
        "sigma": math.sqrt(variance),
        "sigma_obs": math.sqrt(observation_variance),
    }
