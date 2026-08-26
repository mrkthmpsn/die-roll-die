from __future__ import annotations

import numpy as np
import pytest

from die_scouting import InsufficientData, Record, UnsuitableFamily, fit_prior


def gamma_poisson_observations(alpha: float, beta: float, n: int, seed: int = 7) -> list[Record]:
    """Draw `n` observations whose rates come from Gamma(alpha, beta) and whose values are
    Poisson counts at those rates over denominators spanning 5 to 38.
    """
    rng = np.random.default_rng(seed)
    rates = rng.gamma(shape=alpha, scale=1.0 / beta, size=n)
    denominators = rng.uniform(5.0, 38.0, size=n)
    counts = rng.poisson(rates * denominators)
    return [
        Record(entity_id=str(i), value=float(count), denominator=float(denominator))
        for i, (count, denominator) in enumerate(zip(counts, denominators))
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
    rates = np.array([o.value / o.denominator for o in observations])
    uncorrected_alpha = rates.mean() ** 2 / rates.var(ddof=1)

    prior = fit_prior(observations, "gamma", "goals")
    assert prior.params["alpha"] > uncorrected_alpha
    assert uncorrected_alpha < 0.75 * 5.0


def test_min_denominator_excludes_short_observations():
    observations = [
        Record(entity_id="1", value=6.0, denominator=1.0),
        Record(entity_id="2", value=3.0, denominator=10.0),
        Record(entity_id="3", value=9.0, denominator=20.0),
    ]
    with_cameo = fit_prior(observations, "gamma", "goals", min_denominator=0.5)
    without = fit_prior(observations, "gamma", "goals")
    assert with_cameo.params["alpha"] / with_cameo.params["beta"] > (
        without.params["alpha"] / without.params["beta"]
    )


def test_fit_prior_needs_two_observations_above_min_denominator():
    observations = [
        Record(entity_id="1", value=6.0, denominator=1.0),
        Record(entity_id="2", value=3.0, denominator=10.0),
    ]
    with pytest.raises(InsufficientData, match="at least two observations"):
        fit_prior(observations, "gamma", "goals")


def test_fit_prior_rejects_observations_that_are_all_zero():
    observations = [Record(entity_id=str(i), value=0.0, denominator=10.0) for i in range(5)]
    with pytest.raises(InsufficientData, match="value is zero"):
        fit_prior(observations, "gamma", "goals")


def beta_binomial_observations(
    alpha: float, beta: float, n: int, seed: int = 11
) -> list[Record]:
    """Draw `n` observations whose true proportions come from Beta(alpha, beta) and whose
    values are binomial successes over attempts spanning 20 to 200.
    """
    rng = np.random.default_rng(seed)
    proportions = rng.beta(alpha, beta, size=n)
    attempts = rng.integers(20, 200, size=n)
    successes = rng.binomial(attempts, proportions)
    return [
        Record(entity_id=str(i), value=float(s), denominator=float(a))
        for i, (s, a) in enumerate(zip(successes, attempts))
    ]


def normal_observations(
    mu: float, sigma: float, sigma_obs: float, entities: int, seasons: int, seed: int = 13
) -> list[Record]:
    """Draw `seasons` observations each for `entities` entities, whose true levels come from
    Normal(mu, sigma) and whose values are that level over a denominator, plus noise of
    `sigma_obs` per unit of denominator.
    """
    rng = np.random.default_rng(seed)
    records = []
    for entity in range(entities):
        level = rng.normal(mu, sigma)
        for _ in range(seasons):
            denominator = float(rng.uniform(10.0, 30.0))
            rate = level + rng.normal(0.0, sigma_obs / np.sqrt(denominator))
            records.append(
                Record(entity_id=str(entity), value=rate * denominator, denominator=denominator)
            )
    return records


def test_fit_prior_recovers_a_known_beta():
    prior = fit_prior(beta_binomial_observations(6.0, 14.0, 3000), "beta", "pass_completion")
    alpha, beta = prior.params["alpha"], prior.params["beta"]
    assert alpha / (alpha + beta) == pytest.approx(6.0 / 20.0, rel=0.05)
    assert alpha == pytest.approx(6.0, rel=0.25)
    assert beta == pytest.approx(14.0, rel=0.25)


def test_beta_correction_narrows_the_prior():
    observations = beta_binomial_observations(6.0, 14.0, 3000)
    proportions = np.array([o.value / o.denominator for o in observations])
    m, v = proportions.mean(), proportions.var(ddof=1)
    uncorrected = m * (m * (1 - m) / v - 1)

    prior = fit_prior(observations, "beta", "pass_completion")
    assert prior.params["alpha"] > uncorrected


def test_beta_rejects_values_above_their_denominator():
    observations = [
        Record(entity_id="over", value=12.0, denominator=10.0),
        Record(entity_id="fine", value=3.0, denominator=10.0),
    ]
    with pytest.raises(UnsuitableFamily, match="over"):
        fit_prior(observations, "beta", "pass_completion")


def test_fit_prior_recovers_a_known_normal():
    observations = normal_observations(10.0, 1.0, 2.0, entities=400, seasons=4)
    prior = fit_prior(observations, "normal", "distance", min_denominator=0.0)
    assert prior.params["mu"] == pytest.approx(10.0, rel=0.02)
    assert prior.params["sigma"] == pytest.approx(1.0, rel=0.15)
    assert prior.params["sigma_obs"] == pytest.approx(2.0, rel=0.15)


def test_normal_needs_an_entity_with_repeated_observations():
    observations = normal_observations(10.0, 1.0, 2.0, entities=50, seasons=1)
    with pytest.raises(InsufficientData, match="two or more"):
        fit_prior(observations, "normal", "distance", min_denominator=0.0)


def test_both_fit_errors_are_value_errors():
    """Callers catching ValueError keep working, since both types subclass it."""
    assert issubclass(InsufficientData, ValueError)
    assert issubclass(UnsuitableFamily, ValueError)
