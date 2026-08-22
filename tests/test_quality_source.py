from __future__ import annotations

import numpy as np
import pytest

from die_scouting import AnalyticSource, PriorParams, Record


class FakeAdapter:
    def __init__(self, observations: dict[str, list[Record]] | None = None) -> None:
        self.observations = observations or {}

    def get_entity_observations(self, entity_id, stat_id, scope=None):
        return self.observations.get(entity_id, [])

    def get_population_observations(self, stat_id, scope=None):
        return []


def gamma_prior(alpha: float = 3.0, beta: float = 10.0) -> PriorParams:
    """Mean rate of 0.3 goals per ninety."""
    return PriorParams(
        stat_id="non_penalty_goals", family="gamma", params={"alpha": alpha, "beta": beta}
    )


def season(entity_id: str, goals: float, nineties: float) -> Record:
    return Record(entity_id=entity_id, value=goals, exposure=nineties)


def source(observations: dict[str, list[Record]], prior: PriorParams | None = None, seed: int = 0):
    return AnalyticSource(
        prior=prior or gamma_prior(),
        data_adapter=FakeAdapter(observations),
        stat_id="non_penalty_goals",
        rng=np.random.default_rng(seed),
    )


def test_no_observations_returns_the_prior():
    analytic = source({})
    assert analytic.posterior_params("unknown-player") == (3.0, 10.0)


def test_posterior_sums_values_and_exposures():
    analytic = source({"striker": [season("striker", 20, 50), season("striker", 20, 50)]})
    assert analytic.posterior_params("striker") == (43.0, 110.0)


def test_posterior_mean_sits_between_prior_and_observed_rate():
    analytic = source({"striker": [season("striker", 40, 100)]})
    alpha, beta = analytic.posterior_params("striker")
    assert 0.3 < alpha / beta < 0.4


def test_posterior_moves_toward_the_observed_rate_as_exposure_grows():
    thin = source({"p": [season("p", 4, 10)]}).posterior_params("p")
    thick = source({"p": [season("p", 40, 100)]}).posterior_params("p")
    thin_mean = thin[0] / thin[1]
    thick_mean = thick[0] / thick[1]
    assert abs(thick_mean - 0.4) < abs(thin_mean - 0.4)


def test_same_rate_with_less_exposure_gives_a_wider_die():
    """The property the tool exists to show: ten nineties cannot tell you what a hundred can."""
    thin = source({"p": [season("p", 4, 10)]}).sample("p", 50_000)
    thick = source({"p": [season("p", 40, 100)]}).sample("p", 50_000)
    assert np.std(thin) > 2 * np.std(thick)


def test_sample_draws_positive_rates():
    draws = source({"striker": [season("striker", 40, 100)]}).sample("striker", 1000)
    assert len(draws) == 1000
    assert all(d > 0 for d in draws)


def test_predictive_draws_are_whole_numbers():
    draws = source({"striker": [season("striker", 40, 100)]}).sample_predictive(
        "striker", 1000, exposure=30.0
    )
    assert all(d == int(d) for d in draws)


def test_predictive_mean_tracks_posterior_mean_times_exposure():
    analytic = source({"striker": [season("striker", 40, 100)]})
    alpha, beta = analytic.posterior_params("striker")
    draws = analytic.sample_predictive("striker", 50_000, exposure=30.0)
    assert np.mean(draws) == pytest.approx((alpha / beta) * 30.0, rel=0.05)


def test_predictive_at_zero_exposure_scores_nothing():
    draws = source({"striker": [season("striker", 40, 100)]}).sample_predictive(
        "striker", 100, exposure=0.0
    )
    assert set(draws) == {0.0}


def test_predictive_rejects_negative_exposure():
    with pytest.raises(ValueError, match="exposure"):
        source({}).sample_predictive("striker", 10, exposure=-1.0)


def test_a_seeded_generator_repeats_its_draws():
    observations = {"striker": [season("striker", 40, 100)]}
    first = source(observations, seed=7).sample("striker", 100)
    second = source(observations, seed=7).sample("striker", 100)
    assert first == second


def test_unimplemented_family_raises():
    prior = PriorParams(
        stat_id="pass_completion", family="beta", params={"alpha": 2.0, "beta": 5.0}
    )
    analytic = source({}, prior=prior)
    with pytest.raises(NotImplementedError, match="beta"):
        analytic.sample("striker", 10)


def test_gamma_prior_missing_a_parameter_raises():
    prior = PriorParams(stat_id="np_goals", family="gamma", params={"alpha": 3.0})
    with pytest.raises(ValueError, match="beta"):
        source({}, prior=prior).sample("striker", 10)
