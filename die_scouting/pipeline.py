from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np

from .csv_adapter import ColumnMap, CsvDataAdapter
from .data_adapter import DataAdapter
from .die import assemble_die_from_samples
from .fitting import FitReport, fit_scopes, scopes_for
from .models import POSTERIOR_PARAM_NAMES, Die, DieMetadata, Model, PriorParams
from .prior_discovery import fit_prior
from .prior_store import PriorStore
from .quality_sampler import PosteriorSampler


def fit_priors(
    adapter: DataAdapter,
    store: PriorStore,
    stat_id: str,
    model: Model,
    dimension: str | None = None,
    exclude: list[str] | None = None,
    min_denominator: float | None = None,
) -> FitReport:
    """Fit the global prior for `stat_id`, plus one per distinct value of `dimension` when
    it is given, and save them to `store`.

    `exclude` names values of `dimension` to leave unfitted, for a slice known in advance to
    be uninteresting rather than one too thin to fit — those appear in the report instead.

    Returns the `FitReport` from `fit_scopes`, so a scope with too little data to fit appears
    in its `skipped` rather than raising.
    """
    scopes: list[dict[str, str]] = [{}]
    if dimension is not None:
        scopes += [
            scope
            for scope in scopes_for(adapter, stat_id, dimension)
            if scope[dimension] not in (exclude or [])
        ]
    return fit_scopes(adapter, store, stat_id, model, scopes, min_denominator)


def create_die(
    adapter: DataAdapter,
    prior: PriorParams,
    entity_id: str,
    denominator: float,
    n_faces: int = 6,
    strategy: Literal["equal_weight", "equal_width"] = "equal_width",
    draws: int = 100_000,
    entity_name: str | None = None,
    denominator_unit: str | None = None,
    rng: np.random.Generator | None = None,
) -> Die:
    """Build a die over what `entity_id` would record across `denominator`, by updating
    `prior` with that entity's own observations.

    The stat, entity type, scope and model come from `prior`; `denominator` is the amount
    predicted over, whose meaning follows the model, as `PosteriorSampler.sample_predictive`
    describes.

    `entity_name` and `denominator_unit` are carried onto the die's metadata and are
    arguments because `DataAdapter` exposes neither: a label for an entity and a name for
    the denominator's units are properties of the source rather than of a `Record`.

    Raises:
        UnsuitableDenominator: if `denominator` is not positive or, where the model counts
            it, fractional.
        EntityTypeMismatch: if the entity's observations disagree with `prior` about the
            entity type.
    """
    sampler = PosteriorSampler(prior, adapter, prior.stat_id, rng)
    observations = adapter.get_entity_observations(entity_id, prior.stat_id, prior.scope)
    first, second = sampler.posterior_params(entity_id)

    metadata = DieMetadata(
        entity_id=entity_id,
        entity_type=prior.entity_type,
        entity_name=entity_name,
        stat_id=prior.stat_id,
        scope=prior.scope,
        prior=prior,
        posterior_params=dict(zip(POSTERIOR_PARAM_NAMES[prior.model], (first, second))),
        observed_value=sum(o.value for o in observations),
        observed_denominator=sum(o.denominator for o in observations),
        observed_periods=len(observations),
        predicted_denominator=denominator,
        denominator_unit=denominator_unit,
    )
    samples = sampler.sample_predictive(entity_id, draws, denominator)
    return assemble_die_from_samples(samples, n_faces, metadata, strategy)


def build_die_from_csv(
    path: str | Path,
    column_map: ColumnMap,
    stat_id: str,
    model: Model,
    entity_id: str,
    denominator: float,
    scope: dict[str, str] | None = None,
    n_faces: int = 6,
    strategy: Literal["equal_weight", "equal_width"] = "equal_width",
    draws: int = 100_000,
    rng: np.random.Generator | None = None,
) -> Die:
    """Read `path` through `column_map`, fit a prior for `scope` from every entity in it,
    and build a die for `entity_id` over `denominator`.

    The prior is fitted on each call and not stored, so building dies for twenty entities
    fits the same prior twenty times; `fit_priors` and `create_die` are the two-call form
    that fits once. A scope too thin to fit raises here, where `fit_priors` would record it
    in a `FitReport` and carry on.

    `entity_name` and `denominator_unit` are read off `column_map` rather than passed.

    Raises:
        PriorFitError: if the population under `scope` cannot fit `model`.
        UnsuitableDenominator: if `denominator` is not positive or, where the model counts
            it, fractional.
    """
    adapter = CsvDataAdapter(path, column_map)
    scope = scope or {}
    prior = fit_prior(
        adapter.get_population_observations(stat_id, scope), model, stat_id, scope
    )
    return create_die(
        adapter,
        prior,
        entity_id,
        denominator,
        n_faces=n_faces,
        strategy=strategy,
        draws=draws,
        entity_name=adapter.entity_name(entity_id) if column_map.name else None,
        denominator_unit=column_map.denominator,
        rng=rng,
    )
