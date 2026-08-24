from __future__ import annotations

import statistics
from typing import Literal

from .models import PriorParams, Record

MIN_EXPOSURE = 5.0


def fit_prior(
    observations: list[Record],
    family: Literal["beta", "gamma", "normal"],
    stat_id: str,
    scope: dict[str, str] | None = None,
    min_exposure: float = MIN_EXPOSURE,
) -> PriorParams:
    """Fit prior parameters for a stat from population-wide observations, by method of
    moments against `family`.

    `family` is supplied by the caller: it states which values the stat can take at all,
    which no sample establishes, since an unobserved value and an impossible one look
    alike in data.

    Observations with an exposure below `min_exposure` are excluded from the fit, their
    rates being dominated by the small denominator.

    Output is intended to be persisted via a `PriorStore` and re-read, not recomputed
    per call.

    Raises:
        NotImplementedError: if `family` is anything other than "gamma".
    """
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
