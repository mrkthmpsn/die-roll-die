from __future__ import annotations

from .models import PriorParams, Record


def select_family(stat_id: str) -> str:
    """Choose a prior distribution family for a stat by a stat-type heuristic, not an
    automatic goodness-of-fit search: "beta" for bounded rates/proportions, "gamma" for
    non-negative counts or rates, "normal" for roughly symmetric continuous values.
    """
    raise NotImplementedError


def fit_prior(
    observations: list[Record], stat_id: str, scope: dict[str, str] | None = None
) -> PriorParams:
    """Empirical Bayes: fit a prior's parameters from a population's spread of observed
    values, via method of moments against the family chosen by `select_family`.

    Offline/periodic — this is not part of the online per-roll pipeline. Its output is
    meant to be persisted (see `prior_store.PriorStore`) and read, not recomputed live.
    """
    raise NotImplementedError
