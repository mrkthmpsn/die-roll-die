from __future__ import annotations

import pytest
from pydantic import ValidationError

from die_scouting import (
    BootstrapSampler,
    Die,
    DieMetadata,
    Face,
    PosteriorSampler,
    PriorParams,
    Record,
    build_die,
    fit_prior,
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
    assert die.metadata.entity_id is None
    assert die.metadata.extra == {}


def test_fit_prior_needs_observations():
    with pytest.raises(ValueError):
        fit_prior([], "gamma", "goals_per_90")


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


def test_build_die_stamps_the_strategy_and_draw_count():
    samples = [float(i) for i in range(200)]

    die = build_die(samples, n_faces=4, strategy="equal_width")

    assert die.metadata.strategy == "equal_width"
    assert die.metadata.draws == 200


def test_build_die_keeps_the_metadata_it_was_given():
    metadata = DieMetadata(entity_id="3960", stat_id="goals", entity_name="Harry Kane")

    die = build_die([float(i) for i in range(200)], metadata=metadata)

    assert die.metadata.entity_name == "Harry Kane"
    assert die.metadata.stat_id == "goals"
    assert metadata.strategy is None, "the caller's own object is left alone"


def test_metadata_round_trips_through_json():
    metadata = DieMetadata(
        entity_id="3960",
        stat_id="goals",
        scope={"position_general": "Forward"},
        prior=PriorParams(
            stat_id="goals", family="gamma", params={"alpha": 5.26, "beta": 16.59}
        ),
        posterior_params={"alpha": 218.26, "beta": 314.92},
        predicted_denominator=30.0,
        denominator_unit="nineties",
    )
    die = build_die([float(i) for i in range(200)], metadata=metadata)

    restored = Die.model_validate_json(die.model_dump_json())

    assert restored.metadata.scope == {"position_general": "Forward"}
    assert restored.metadata.prior.family == "gamma"
    assert restored.metadata.posterior_params["beta"] == 314.92
    assert restored.metadata.denominator_unit == "nineties"


def test_two_scopes_give_dice_that_can_be_told_apart():
    samples = [float(i) for i in range(200)]
    forwards = build_die(samples, metadata=DieMetadata(scope={"position_general": "Forward"}))
    global_ = build_die(samples, metadata=DieMetadata())

    assert forwards.metadata.scope != global_.metadata.scope
