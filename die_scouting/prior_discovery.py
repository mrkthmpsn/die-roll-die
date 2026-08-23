from __future__ import annotations

import statistics

from .models import PriorParams, Record

STAT_FAMILIES: dict[str, str] = {
    "appearances": "gamma",
    "assists": "gamma",
    "goals": "gamma",
    "headed_shots": "gamma",
    "non_penalty_goals": "gamma",
    "penalty_goals": "gamma",
    "shots": "gamma",
}

MIN_EXPOSURE = 5.0


def select_family(stat_id: str) -> str:
    """Return the prior distribution family registered for `stat_id` in `STAT_FAMILIES`:
    "beta" for bounded rates/proportions, "gamma" for non-negative counts or rates,
    "normal" for roughly symmetric continuous values.

    Raises:
        ValueError: if `stat_id` has no entry in `STAT_FAMILIES`.
    """
    try:
        return STAT_FAMILIES[stat_id]
    except KeyError:
        raise ValueError(
            f"no prior family is registered for stat {stat_id!r}; "
            f"registered stats are {', '.join(sorted(STAT_FAMILIES))}"
        ) from None


def fit_prior(
    observations: list[Record],
    stat_id: str,
    scope: dict[str, str] | None = None,
    min_exposure: float = MIN_EXPOSURE,
) -> PriorParams:
    """Fit prior parameters for a stat from population-wide observations, by method of
    moments against the family given by `select_family`.

    Observations with an exposure below `min_exposure` are excluded from the fit, their
    rates being dominated by the small denominator.

    Output is intended to be persisted via a `PriorStore` and re-read, not recomputed
    per call.

    Raises:
        NotImplementedError: if the family for `stat_id` is anything other than "gamma".
    """
    family = select_family(stat_id)
    if family != "gamma":
        raise NotImplementedError(f"fitting a prior of family {family!r} is not implemented")
    return PriorParams(
        stat_id=stat_id,
        scope=scope or {},
        family=family,
        params=_fit_gamma(observations, min_exposure),
    )


def _fit_gamma(observations: list[Record], min_exposure: float) -> dict[str, float]:
    """Return `alpha` and `beta` for a gamma over the observations' rates, matched to the
    rates' mean and to their variance less the variance a Poisson count contributes.

    A rate `value / exposure` varies both with the spread of true rates and with the
    randomness of the count itself, the latter contributing `mean / exposure`. Subtracting
    its average across the observations leaves the spread the prior should carry; where
    the subtraction is not positive, the uncorrected variance is used, giving a wider
    prior.

    Raises:
        ValueError: if fewer than two observations reach `min_exposure`, or if their rates
            have a mean or a variance of zero.
    """
    usable = [o for o in observations if o.exposure >= min_exposure]
    if len(usable) < 2:
        raise ValueError(
            f"fitting a gamma prior needs at least two observations of exposure "
            f"{min_exposure} or more; got {len(usable)}"
        )

    rates = [o.value / o.exposure for o in usable]
    mean = statistics.fmean(rates)
    if mean <= 0:
        raise ValueError("the observations' mean rate is zero, so no gamma fits them")

    observed_variance = statistics.variance(rates)
    poisson_variance = mean * statistics.fmean(1.0 / o.exposure for o in usable)
    variance = observed_variance - poisson_variance
    if variance <= 0:
        variance = observed_variance
    if variance <= 0:
        raise ValueError("the observations' rates are all equal, so no gamma fits them")

    return {"alpha": mean**2 / variance, "beta": mean / variance}
