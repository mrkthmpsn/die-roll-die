from __future__ import annotations

import numpy as np
import pytest

from die_roll_die import (
    ColumnMap,
    CsvDataAdapter,
    InMemoryPriorStore,
    InsufficientData,
    UnsuitableDenominator,
    build_die_from_csv,
    create_die,
    fit_priors,
)

CSV = """\
player_source_id,player_name,season_name,position_general,appearances,goals
1,Alice Adeyemi,2023/24,Forward,30,12
1,Alice Adeyemi,2024/25,Forward,32,15
2,Bo Bergstrom,2023/24,Forward,28,9
2,Bo Bergstrom,2024/25,Forward,25,7
3,Cara Costa,2023/24,Forward,34,18
3,Cara Costa,2024/25,Forward,30,14
4,Dev Dhillon,2023/24,Midfielder,31,4
4,Dev Dhillon,2024/25,Midfielder,29,6
5,Eze Effiong,2023/24,Midfielder,33,3
5,Eze Effiong,2024/25,Midfielder,27,5
6,Fay Fontaine,2023/24,Goalkeeper,30,0
6,Fay Fontaine,2024/25,Goalkeeper,32,0
"""

COLUMNS = ColumnMap(
    entity="player_source_id",
    entity_type="player",
    denominator="appearances",
    name="player_name",
    dimensions=("season_name", "position_general"),
)


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "player_seasons.csv"
    path.write_text(CSV, encoding="utf-8")
    return path


@pytest.fixture
def adapter(csv_path):
    return CsvDataAdapter(csv_path, COLUMNS)


def test_the_two_call_route_runs_from_a_csv_to_a_die(adapter):
    store = InMemoryPriorStore()
    fit_priors(adapter, store, "goals", "gamma_poisson", min_denominator=1.0)
    prior = store.get("player", "goals", {})
    die = create_die(
        adapter,
        prior,
        "1",
        denominator=30,
        n_faces=6,
        entity_name=adapter.entity_name("1"),
        denominator_unit="appearances",
        rng=np.random.default_rng(0),
    )
    assert len(die.faces) == 6
    assert sum(face.weight for face in die.faces) == pytest.approx(1.0)


def test_the_die_carries_the_metadata_a_consumer_reads(adapter):
    store = InMemoryPriorStore()
    fit_priors(adapter, store, "goals", "gamma_poisson", min_denominator=1.0)
    prior = store.get("player", "goals", {})
    die = create_die(
        adapter, prior, "1", 30, entity_name="Alice Adeyemi", denominator_unit="appearances"
    )
    meta = die.metadata
    assert (meta.entity_id, meta.entity_type, meta.entity_name) == ("1", "player", "Alice Adeyemi")
    assert meta.stat_id == "goals"
    assert meta.prior == prior
    assert set(meta.posterior_params) == {"alpha", "beta"}
    assert (meta.observed_value, meta.observed_denominator) == (27.0, 62.0)
    assert meta.observed_periods == 2
    assert (meta.predicted_denominator, meta.denominator_unit) == (30.0, "appearances")
    assert meta.draws == 100_000


def test_a_scoped_prior_carries_its_scope_onto_the_die(adapter):
    store = InMemoryPriorStore()
    fit_priors(adapter, store, "goals", "gamma_poisson", "position_general", min_denominator=1.0)
    prior = store.get("player", "goals", {"position_general": "Forward"})
    die = create_die(adapter, prior, "1", 30)
    assert die.metadata.scope == {"position_general": "Forward"}


def test_a_scope_with_nothing_to_estimate_from_is_skipped_rather_than_raising(adapter):
    store = InMemoryPriorStore()
    report = fit_priors(
        adapter, store, "goals", "gamma_poisson", "position_general", min_denominator=1.0
    )
    assert {"position_general": "Forward"} in report.fitted
    assert [scope for scope, _ in report.skipped] == [{"position_general": "Goalkeeper"}]


def test_the_one_call_route_matches_the_two_call_route(csv_path, adapter):
    store = InMemoryPriorStore()
    fit_priors(adapter, store, "goals", "gamma_poisson", min_denominator=1.0)
    stepwise = create_die(
        adapter,
        store.get("player", "goals", {}),
        "1",
        30,
        entity_name="Alice Adeyemi",
        denominator_unit="appearances",
        rng=np.random.default_rng(7),
    )
    one_call = build_die_from_csv(
        csv_path,
        COLUMNS,
        "goals",
        "gamma_poisson",
        "1",
        30,
        rng=np.random.default_rng(7),
    )
    assert [f.value_range for f in one_call.faces] == [f.value_range for f in stepwise.faces]
    assert one_call.metadata.entity_name == "Alice Adeyemi"
    assert one_call.metadata.denominator_unit == "appearances"


def test_the_one_call_route_raises_on_a_scope_it_cannot_fit(csv_path):
    with pytest.raises(InsufficientData):
        build_die_from_csv(
            csv_path,
            COLUMNS,
            "goals",
            "gamma_poisson",
            "6",
            30,
            scope={"position_general": "Goalkeeper"},
        )


def test_create_die_rejects_a_zero_denominator_under_either_strategy(adapter):
    """`equal_weight` used to return six faces of `(0.0, 0.0)`, which serialises and renders
    as a prediction; `equal_width` failed inside binning, three calls from the argument.
    """
    store = InMemoryPriorStore()
    fit_priors(adapter, store, "goals", "gamma_poisson", min_denominator=1.0)
    prior = store.get("player", "goals", {})

    for strategy in ("equal_weight", "equal_width"):
        with pytest.raises(UnsuitableDenominator, match="zero opportunity"):
            create_die(adapter, prior, "1", denominator=0, strategy=strategy)
