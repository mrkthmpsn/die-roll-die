from __future__ import annotations

import numpy as np
import pytest

from die_scouting import PosteriorSampler, PriorParams, Record


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
    return Record(entity_id=entity_id, value=goals, denominator=nineties)


def source(observations: dict[str, list[Record]], prior: PriorParams | None = None, seed: int = 0):
    return PosteriorSampler(
        prior=prior or gamma_prior(),
        data_adapter=FakeAdapter(observations),
        stat_id="non_penalty_goals",
        rng=np.random.default_rng(seed),
    )


def test_no_observations_returns_the_prior():
    analytic = source({})
    assert analytic.posterior_params("unknown-player") == (3.0, 10.0)


def test_posterior_sums_values_and_denominators():
    analytic = source({"striker": [season("striker", 20, 50), season("striker", 20, 50)]})
    assert analytic.posterior_params("striker") == (43.0, 110.0)


def test_posterior_mean_sits_between_prior_and_observed_rate():
    analytic = source({"striker": [season("striker", 40, 100)]})
    alpha, beta = analytic.posterior_params("striker")
    assert 0.3 < alpha / beta < 0.4


def test_posterior_moves_toward_the_observed_rate_as_the_denominator_grows():
    thin = source({"p": [season("p", 4, 10)]}).posterior_params("p")
    thick = source({"p": [season("p", 40, 100)]}).posterior_params("p")
    thin_mean = thin[0] / thin[1]
    thick_mean = thick[0] / thick[1]
    assert abs(thick_mean - 0.4) < abs(thin_mean - 0.4)


def test_same_rate_with_a_smaller_denominator_gives_a_wider_die():
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
        "striker", 1000, denominator=30.0
    )
    assert all(d == int(d) for d in draws)


def test_predictive_mean_tracks_posterior_mean_times_denominator():
    analytic = source({"striker": [season("striker", 40, 100)]})
    alpha, beta = analytic.posterior_params("striker")
    draws = analytic.sample_predictive("striker", 50_000, denominator=30.0)
    assert np.mean(draws) == pytest.approx((alpha / beta) * 30.0, rel=0.05)


def test_predictive_at_a_zero_denominator_scores_nothing():
    draws = source({"striker": [season("striker", 40, 100)]}).sample_predictive(
        "striker", 100, denominator=0.0
    )
    assert set(draws) == {0.0}


def test_predictive_rejects_a_negative_denominator():
    with pytest.raises(ValueError, match="denominator"):
        source({}).sample_predictive("striker", 10, denominator=-1.0)


def test_a_seeded_generator_repeats_its_draws():
    observations = {"striker": [season("striker", 40, 100)]}
    first = source(observations, seed=7).sample("striker", 100)
    second = source(observations, seed=7).sample("striker", 100)
    assert first == second


def beta_prior(alpha: float = 2.0, beta: float = 8.0) -> PriorParams:
    """Mean proportion of 0.2."""
    return PriorParams(
        stat_id="pass_completion", family="beta", params={"alpha": alpha, "beta": beta}
    )


def normal_prior(mu: float = 10.0, sigma: float = 1.0, sigma_obs: float = 2.0) -> PriorParams:
    return PriorParams(
        stat_id="distance",
        family="normal",
        params={"mu": mu, "sigma": sigma, "sigma_obs": sigma_obs},
    )


def test_beta_posterior_adds_successes_and_failures():
    observations = {"passer": [season("passer", 30, 100), season("passer", 10, 50)]}
    alpha, beta = source(observations, prior=beta_prior()).posterior_params("passer")
    assert (alpha, beta) == (2.0 + 40, 8.0 + 110)


def test_beta_draws_stay_within_zero_and_one():
    observations = {"passer": [season("passer", 30, 100)]}
    draws = source(observations, prior=beta_prior()).sample("passer", 500)
    assert all(0.0 <= d <= 1.0 for d in draws)


def test_beta_predictive_counts_successes_out_of_attempts():
    observations = {"passer": [season("passer", 30, 100)]}
    draws = source(observations, prior=beta_prior()).sample_predictive("passer", 500, 40)
    assert all(0.0 <= d <= 40.0 and d == int(d) for d in draws)
    assert np.mean(draws) == pytest.approx(40 * 32 / 118, rel=0.15)


def test_beta_predictive_rejects_fractional_attempts():
    with pytest.raises(ValueError, match="whole number of attempts"):
        source({}, prior=beta_prior()).sample_predictive("passer", 10, 12.5)


def test_normal_posterior_moves_towards_the_observations():
    observations = {"runner": [season("runner", 130.0, 10.0)]}
    mu, sigma = source(observations, prior=normal_prior()).posterior_params("runner")
    assert 10.0 < mu < 13.0
    assert sigma < 1.0


def test_normal_posterior_with_no_observations_returns_the_prior():
    mu, sigma = source({}, prior=normal_prior()).posterior_params("runner")
    assert (mu, sigma) == (10.0, 1.0)


def test_normal_draws_can_be_either_side_of_the_mean():
    draws = source({}, prior=normal_prior()).sample("runner", 1000)
    assert min(draws) < 10.0 < max(draws)


def test_normal_predictive_totals_over_the_denominator():
    draws = source({}, prior=normal_prior()).sample_predictive("runner", 2000, 10.0)
    assert np.mean(draws) == pytest.approx(100.0, rel=0.05)


def test_gamma_prior_missing_a_parameter_raises():
    prior = PriorParams(stat_id="np_goals", family="gamma", params={"alpha": 3.0})
    with pytest.raises(ValueError, match="beta"):
        source({}, prior=prior).sample("striker", 10)
