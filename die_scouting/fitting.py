from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .data_adapter import DataAdapter
from .errors import InsufficientData
from .prior_discovery import fit_prior
from .prior_store import PriorStore


class FitReport(BaseModel):
    """What a run of `fit_scopes` produced: the scopes whose priors were saved, and the
    scopes it could not fit, each with the reason.
    """

    fitted: list[dict[str, str]] = []
    skipped: list[tuple[dict[str, str], str]] = []


def scopes_for(adapter: DataAdapter, stat_id: str, column: str) -> list[dict[str, str]]:
    """Return one scope per distinct value of `column` across the population's observations
    for `stat_id`, taken from each Record's `context`.

    Observations whose context lacks `column`, or holds an empty value for it, are ignored.

    Raises:
        ValueError: if no observation carries a value for `column`.
    """
    values = {
        record.context[column]
        for record in adapter.get_population_observations(stat_id)
        if record.context.get(column)
    }
    if not values:
        raise ValueError(f"no observation of {stat_id!r} carries a value for {column!r}")
    return [{column: value} for value in sorted(values)]


def fit_scopes(
    adapter: DataAdapter,
    store: PriorStore,
    stat_id: str,
    family: Literal["beta", "gamma", "normal"],
    scopes: list[dict[str, str]],
    min_denominator: float | None = None,
) -> FitReport:
    """Fit a prior for each scope and save those that fit, returning a `FitReport`.

    A scope raising `InsufficientData` is recorded in the report's `skipped` and the run
    continues, a thin slice being expected when scopes are enumerated from a column. An
    `UnsuitableFamily` is not caught, since it says `family` is wrong for `stat_id` rather
    than for one slice.
    """
    report = FitReport()
    for scope in scopes:
        observations = adapter.get_population_observations(stat_id, scope)
        try:
            if min_denominator is None:
                params = fit_prior(observations, family, stat_id, scope)
            else:
                params = fit_prior(observations, family, stat_id, scope, min_denominator)
        except InsufficientData as error:
            report.skipped.append((scope, str(error)))
            continue
        store.save(params)
        report.fitted.append(scope)
    return report
