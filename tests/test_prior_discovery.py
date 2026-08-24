from __future__ import annotations

import numpy as np
import pytest

from die_scouting import Record, fit_prior


def gamma_poisson_observations(alpha: float, beta: float, n: int, seed: int = 7) -> list[Record]:
    """Draw `n` observations whose rates come from Gamma(alpha, beta) and whose values are
    Poisson counts at those rates over exposures spanning 5 to 38.
    """
    rng = np.random.default_rng(seed)
    rates = rng.gamma(shape=alpha, scale=1.0 / beta, size=n)
    exposures = rng.uniform(5.0, 38.0, size=n)
    counts = rng.poisson(rates * exposures)
    return [
        Record(entity_id=str(i), value=float(count), exposure=float(exposure))
        for i, (count, exposure) in enumerate(zip(counts, exposures))
    ]


def test_fit_prior_records_the_stat_and_scope():
    scope = {"position_general": "Forward"}
    prior = fit_prior(gamma_poisson_observations(5.0, 16.0, 200), "gamma", "goals", scope)
    assert prior.stat_id == "goals"
    assert prior.scope == scope
    assert prior.family == "gamma"
    assert set(prior.params) == {"alpha", "beta"}


def test_fit_prior_recovers_a_known_gamma():
    prior = fit_prior(gamma_poisson_observations(5.0, 16.0, 4000), "gamma", "goals")
    alpha, beta = prior.params["alpha"], prior.params["beta"]
    assert alpha / beta == pytest.approx(5.0 / 16.0, rel=0.05)
    assert alpha == pytest.approx(5.0, rel=0.15)
    assert beta == pytest.approx(16.0, rel=0.15)


def test_correcting_for_poisson_noise_narrows_the_prior():
    observations = gamma_poisson_observations(5.0, 16.0, 4000)
    rates = np.array([o.value / o.exposure for o in observations])
    uncorrected_alpha = rates.mean() ** 2 / rates.var(ddof=1)

    prior = fit_prior(observations, "gamma", "goals")
    assert prior.params["alpha"] > uncorrected_alpha
    assert uncorrected_alpha < 0.75 * 5.0


def test_min_exposure_excludes_short_observations():
    observations = [
        Record(entity_id="1", value=6.0, exposure=1.0),
        Record(entity_id="2", value=3.0, exposure=10.0),
        Record(entity_id="3", value=9.0, exposure=20.0),
    ]
    with_cameo = fit_prior(observations, "gamma", "goals", min_exposure=0.5)
    without = fit_prior(observations, "gamma", "goals")
    assert with_cameo.params["alpha"] / with_cameo.params["beta"] > (
        without.params["alpha"] / without.params["beta"]
    )


def test_fit_prior_needs_two_observations_above_min_exposure():
    observations = [
        Record(entity_id="1", value=6.0, exposure=1.0),
        Record(entity_id="2", value=3.0, exposure=10.0),
    ]
    with pytest.raises(ValueError, match="at least two observations"):
        fit_prior(observations, "gamma", "goals")


def test_fit_prior_rejects_observations_that_are_all_zero():
    observations = [Record(entity_id=str(i), value=0.0, exposure=10.0) for i in range(5)]
    with pytest.raises(ValueError, match="mean rate is zero"):
        fit_prior(observations, "gamma", "goals")


def test_fit_prior_rejects_a_family_it_cannot_fit():
    with pytest.raises(NotImplementedError, match="beta"):
        fit_prior(gamma_poisson_observations(5.0, 16.0, 50), "beta", "pass_completion")
