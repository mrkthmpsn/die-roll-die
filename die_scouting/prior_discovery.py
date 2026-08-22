from __future__ import annotations

from .models import PriorParams, Record


def select_family(stat_id: str) -> str:
    """Choose a prior distribution family for a stat by a stat-type heuristic: "beta" for
    bounded rates/proportions, "gamma" for non-negative counts or rates, "normal" for
    roughly symmetric continuous values.
    """
    raise NotImplementedError


def fit_prior(
    observations: list[Record], stat_id: str, scope: dict[str, str] | None = None
) -> PriorParams:
    """Fit prior parameters for a stat from population-wide observations, by method of
    moments against the family given by `select_family`.

    Output is intended to be persisted via a `PriorStore` and re-read, not recomputed
    per call.
    """
    raise NotImplementedError
