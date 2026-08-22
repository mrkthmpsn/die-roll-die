from __future__ import annotations

import pytest
from pydantic import ValidationError

from die_scouting import (
    AnalyticSource,
    BootstrapSource,
    Die,
    Face,
    PriorParams,
    Record,
    build_die,
    fit_prior,
    resolve_prior,
    select_family,
)


def test_record_instantiates():
    record = Record(entity_id="player-1", value=12.0, exposure=30.0)
    assert record.context == {}


def test_record_requires_exposure():
    with pytest.raises(ValidationError):
        Record(entity_id="player-1", value=12.0)


def test_prior_params_instantiates():
    prior = PriorParams(stat_id="goals_per_90", family="beta", params={"alpha": 2.0, "beta": 5.0})
    assert prior.scope == {}


def test_face_and_die_instantiate():
    face = Face(label="1", weight=0.5, value_range=(0.0, 1.0))
    die = Die(faces=[face])
    assert die.metadata == {}


def test_prior_discovery_stubs_raise():
    with pytest.raises(NotImplementedError):
        select_family("goals_per_90")
    with pytest.raises(NotImplementedError):
        fit_prior([], "goals_per_90")


def test_prior_store_resolve_stub_raises():
    class FakeStore:
        def save(self, params):
            pass

        def get(self, stat_id, scope):
            return None

    with pytest.raises(NotImplementedError):
        resolve_prior(FakeStore(), "goals_per_90", {})


def test_quality_source_stubs_raise():
    class FakeAdapter:
        def get_entity_observations(self, entity_id, stat_id, scope=None):
            return []

        def get_population_observations(self, stat_id, scope=None):
            return []

    prior = PriorParams(stat_id="goals_per_90", family="beta", params={"alpha": 2.0, "beta": 5.0})
    analytic = AnalyticSource(prior=prior, data_adapter=FakeAdapter(), stat_id="goals_per_90")
    bootstrap = BootstrapSource(data_adapter=FakeAdapter(), stat_id="goals_per_90")
    with pytest.raises(NotImplementedError):
        analytic.sample("player-1", 100)
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
