from __future__ import annotations

import numpy as np
import pytest

from die_scouting import (
    POSTERIOR_PARAM_NAMES,
    BootstrapSampler,
    EntityTypeMismatch,
    InsufficientObservations,
    MissingPriorParam,
    PosteriorSampler,
    PriorParams,
    Record,
    UnsuitableDenominator,
)


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
        entity_type="player",
        stat_id="non_penalty_goals", model="gamma_poisson", params={"alpha": alpha, "beta": beta}
    )


def season(entity_id: str, goals: float, nineties: float) -> Record:
    return Record(entity_type="player", entity_id=entity_id, value=goals, denominator=nineties)


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


def test_predictive_rejects_a_zero_denominator():
    """Every draw would be zero, which is one outcome rather than a spread."""
    with pytest.raises(UnsuitableDenominator, match="zero opportunity"):
        source({"striker": [season("striker", 40, 100)]}).sample_predictive(
            "striker", 100, denominator=0.0
        )


def test_predictive_rejects_a_negative_denominator():
    with pytest.raises(UnsuitableDenominator, match="denominator"):
        source({}).sample_predictive("striker", 10, denominator=-1.0)


def test_a_seeded_generator_repeats_its_draws():
    observations = {"striker": [season("striker", 40, 100)]}
    first = source(observations, seed=7).sample("striker", 100)
    second = source(observations, seed=7).sample("striker", 100)
    assert first == second


def beta_prior(alpha: float = 2.0, beta: float = 8.0) -> PriorParams:
    """Mean proportion of 0.2."""
    return PriorParams(
        entity_type="player",
        stat_id="pass_completion", model="beta_binomial", params={"alpha": alpha, "beta": beta}
    )


def normal_prior(mu: float = 10.0, sigma: float = 1.0, sigma_obs: float = 2.0) -> PriorParams:
    return PriorParams(
        entity_type="player",
        stat_id="distance",
        model="normal_normal",
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
    with pytest.raises(UnsuitableDenominator, match="whole number of attempts"):
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
    prior = PriorParams(entity_type="player", stat_id="np_goals", model="gamma_poisson", params={"alpha": 3.0})
    with pytest.raises(MissingPriorParam, match="beta"):
        source({}, prior=prior).sample("striker", 10)


def test_a_prior_for_another_entity_type_is_rejected():
    observations = {"striker": [season("striker", 40, 100)]}
    club_prior = gamma_prior().model_copy(update={"entity_type": "club"})
    with pytest.raises(EntityTypeMismatch, match="describes a 'club'"):
        source(observations, prior=club_prior).sample("striker", 10)


def exponential_prior(alpha: float = 6.0, beta: float = 2.0) -> PriorParams:
    """Mean rate of 3 events per unit of time."""
    return PriorParams(
        entity_type="player",
        stat_id="downtime",
        model="gamma_exponential",
        params={"alpha": alpha, "beta": beta},
    )


def test_gamma_exponential_adds_events_to_alpha_and_time_to_beta():
    observations = {"press": [season("press", 20.0, 50.0), season("press", 10.0, 25.0)]}
    alpha, beta = source(observations, prior=exponential_prior()).posterior_params("press")
    assert (alpha, beta) == (6.0 + 75.0, 2.0 + 30.0)


def test_both_gamma_models_agree_when_given_the_same_events_and_time():
    """The update is shared; only which Record field holds which quantity differs."""
    poisson = {"p": [season("p", 30.0, 12.0)]}
    exponential = {"p": [season("p", 12.0, 30.0)]}

    counts = source(poisson, prior=gamma_prior(6.0, 2.0)).posterior_params("p")
    times = source(exponential, prior=exponential_prior(6.0, 2.0)).posterior_params("p")

    assert counts == times


def test_gamma_exponential_predicts_a_positive_total_time():
    observations = {"press": [season("press", 20.0, 50.0)]}
    draws = source(observations, prior=exponential_prior()).sample_predictive("press", 500, 10)
    assert all(d > 0 for d in draws)
    assert not all(float(d).is_integer() for d in draws), "time is continuous"


def test_gamma_exponential_predicts_over_a_whole_number_of_events():
    with pytest.raises(UnsuitableDenominator, match="whole number of events"):
        source({}, prior=exponential_prior()).sample_predictive("press", 10, 7.5)


@pytest.mark.parametrize(
    "model, params",
    [
        ("gamma_poisson", {"alpha": 3.0, "beta": 10.0}),
        ("gamma_exponential", {"alpha": 3.0, "beta": 10.0}),
        ("beta_binomial", {"alpha": 3.0, "beta": 10.0}),
        ("normal_normal", {"mu": 3.0, "sigma": 10.0, "sigma_obs": 2.0}),
    ],
)
def test_posterior_params_come_back_under_the_names_the_mapping_gives(model, params):
    """An entity with no observations returns the prior unchanged, so zipping the mapping's
    names onto the pair must reproduce the prior's own params — which it can only do if the
    names are in the order the pair comes out in."""
    prior = PriorParams(entity_type="player", stat_id="s", model=model, params=params)
    analytic = source({}, prior=prior)
    names = POSTERIOR_PARAM_NAMES[model]
    assert dict(zip(names, analytic.posterior_params("unknown"))) == {k: params[k] for k in names}


def test_a_normal_prior_without_sigma_obs_is_rejected():
    prior = PriorParams(
        entity_type="player", stat_id="s", model="normal_normal", params={"mu": 3.0, "sigma": 1.0}
    )
    with pytest.raises(MissingPriorParam, match="sigma_obs"):
        source({}, prior=prior).posterior_params("unknown")


def resampler(observations: dict[str, list[Record]], seed: int = 0) -> BootstrapSampler:
    return BootstrapSampler(
        data_adapter=FakeAdapter(observations),
        stat_id="non_penalty_goals",
        rng=np.random.default_rng(seed),
    )


def test_bootstrap_returns_the_number_of_draws_asked_for():
    bootstrap = resampler({"striker": [season("striker", 10, 30), season("striker", 20, 30)]})
    assert len(bootstrap.sample("striker", 500)) == 500


def test_a_seeded_bootstrap_repeats_its_draws():
    records = {"striker": [season("striker", 10, 30), season("striker", 20, 30)]}
    assert resampler(records, seed=7).sample("striker", 50) == resampler(
        records, seed=7
    ).sample("striker", 50)


def test_bootstrap_draws_vary_across_resamples():
    bootstrap = resampler({"striker": [season("striker", 3, 30), season("striker", 21, 30)]})
    assert len(set(bootstrap.sample("striker", 200))) > 1


def test_no_draw_leaves_the_range_of_the_observed_rates():
    bootstrap = resampler(
        {
            "striker": [
                season("striker", 3, 30),
                season("striker", 12, 30),
                season("striker", 21, 30),
            ]
        }
    )
    draws = bootstrap.sample("striker", 500)
    assert min(draws) >= 0.1, "the worst season's rate"
    assert max(draws) <= 0.7, "the best season's rate"


def match_career(entity_id: str) -> list[Record]:
    """Sixty appearances holding 30 goals in 51 nineties, denominators varying only as a
    substitute's do.
    """
    goals = [1.0, 0.0, 0.0, 2.0, 0.0, 0.0] * 10
    nineties = [1.0, 1.0, 0.4, 1.0, 0.7, 1.0] * 10
    return [
        Record(entity_type="player", entity_id=entity_id, value=goal, denominator=ninety)
        for goal, ninety in zip(goals, nineties)
    ]


def test_bootstrap_draws_centre_on_the_pooled_rate():
    """Case resampling draws whole records, so a draw is a ratio of sums rather than a
    mean of rates. Across rows whose denominators are close, that ratio's bias is smaller
    than the Monte Carlo error of five thousand draws.
    """
    bootstrap = resampler({"striker": match_career("striker")})
    draws = bootstrap.sample("striker", 5000)
    assert sum(draws) / len(draws) == pytest.approx(30 / 51, abs=0.01)


def test_the_ratio_of_sums_is_biased_when_denominators_differ():
    """Three seasons of 10/20, 20/30 and 6/50 pool to 0.36, while resampling three of them
    with replacement has an expectation of 0.3869 across the 27 equally likely resamples.
    Each resample counts once however much exposure it drew, and the resamples that omit
    the 50-ninety row are both the short ones and the high-rate ones, so the draws centre
    above the pooled rate.
    """
    bootstrap = resampler(
        {"striker": [season("striker", 10, 20), season("striker", 20, 30), season("striker", 6, 50)]}
    )
    draws = bootstrap.sample("striker", 5000)
    mean = sum(draws) / len(draws)
    assert mean == pytest.approx(0.3869, abs=0.01)
    assert mean > 36 / 100, "the pooled rate, which the draws do not centre on"


def test_identical_observations_resample_to_one_rate():
    bootstrap = resampler({"striker": [season("striker", 12, 30), season("striker", 12, 30)]})
    assert set(bootstrap.sample("striker", 100)) == {0.4}


def test_bootstrap_rejects_a_single_observation():
    bootstrap = resampler({"striker": [season("striker", 12, 30)]})
    with pytest.raises(InsufficientObservations, match="at least 2"):
        bootstrap.sample("striker", 100)


def test_bootstrap_rejects_an_entity_with_no_observations():
    with pytest.raises(InsufficientObservations, match="at least 2"):
        resampler({}).sample("unknown-player", 100)


def test_bootstrap_rejects_a_denominator_of_zero():
    bootstrap = resampler({"striker": [season("striker", 12, 30), season("striker", 0, 0)]})
    with pytest.raises(UnsuitableDenominator, match="denominator"):
        bootstrap.sample("striker", 100)


def test_the_sampler_errors_are_value_errors():
    """Callers catching ValueError keep working, since all four types subclass it."""
    assert issubclass(EntityTypeMismatch, ValueError)
    assert issubclass(MissingPriorParam, ValueError)
    assert issubclass(UnsuitableDenominator, ValueError)
    assert issubclass(InsufficientObservations, ValueError)
