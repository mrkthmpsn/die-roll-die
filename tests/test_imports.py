from __future__ import annotations

import pytest
from pydantic import ValidationError

from die_scouting import (
    PosteriorSampler,
    BootstrapSampler,
    Die,
    Face,
    PriorParams,
    Record,
    build_die,
    fit_prior,
    resolve_prior,
)


def test_record_instantiates():
    record = Record(entity_id="player-1", value=12.0, denominator=30.0)
    assert record.context == {}


def test_record_requires_a_denominator():
    with pytest.raises(ValidationError):
        Record(entity_id="player-1", value=12.0)


def test_prior_params_instantiates():
    prior = PriorParams(stat_id="goals_per_90", family="beta", params={"alpha": 2.0, "beta": 5.0})
    assert prior.scope == {}


def test_face_and_die_instantiate():
    face = Face(label="1", weight=0.5, value_range=(0.0, 1.0))
    die = Die(faces=[face])
    assert die.metadata == {}


def test_fit_prior_needs_observations():
    with pytest.raises(ValueError):
        fit_prior([], "gamma", "goals_per_90")


def test_prior_store_resolve_stub_raises():
    class FakeStore:
        def save(self, params):
            pass

        def get(self, stat_id, scope):
            return None

    with pytest.raises(NotImplementedError):
        resolve_prior(FakeStore(), "goals_per_90", {})


def test_bootstrap_source_stub_raises():
    class FakeAdapter:
        def get_entity_observations(self, entity_id, stat_id, scope=None):
            return []

        def get_population_observations(self, stat_id, scope=None):
            return []

    bootstrap = BootstrapSampler(data_adapter=FakeAdapter(), stat_id="goals_per_90")
    with pytest.raises(NotImplementedError):
        bootstrap.sample("player-1", 100)


def test_build_die_builds_a_real_die():
    samples = [float(i) for i in range(100)]
    die = build_die(samples, n_faces=6)
    assert len(die.faces) == 6
    assert sum(f.weight for f in die.faces) == pytest.approx(1.0)


def test_build_die_supports_d20():
    samples = [float(i) for i in range(1000)]
    die = build_die(samples, n_faces=20)
    assert len(die.faces) == 20


def test_build_die_passes_the_strategy_through():
    samples = [float(i) for i in range(100)] + [50.0] * 100

    equal_mass = build_die(samples, n_faces=4)
    equal_width = build_die(samples, n_faces=4, strategy="equal_width")

    mass_weights = {round(f.weight, 6) for f in equal_mass.faces}
    width_widths = {round(f.value_range[1] - f.value_range[0], 6) for f in equal_width.faces}
    assert len(mass_weights) == 1
    assert len(width_widths) == 1
    assert len({round(f.weight, 6) for f in equal_width.faces}) > 1
