from __future__ import annotations

import json

import pytest

from die_scouting import (
    PRIOR_STORE_SCHEMA_VERSION,
    InMemoryPriorStore,
    JsonPriorStore,
    PriorParams,
    UnreadablePriorStore,
)

FORWARD = {"position_general": "Forward"}


def prior(scope: dict[str, str], alpha: float = 5.0, stat_id: str = "goals") -> PriorParams:
    return PriorParams(
        stat_id=stat_id,
        entity_type="player",
        scope=scope,
        model="gamma_poisson",
        params={"alpha": alpha, "beta": 16.0},
    )


@pytest.fixture(params=["memory", "json"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryPriorStore()
    return JsonPriorStore(tmp_path / "priors.json")


def test_a_saved_prior_comes_back(store):
    store.save(prior(FORWARD))
    assert store.get("player", "goals", FORWARD).params["alpha"] == 5.0


def test_an_unsaved_scope_is_a_miss(store):
    store.save(prior(FORWARD))
    assert store.get("player", "goals", {"position_general": "Defender"}) is None
    assert store.get("player", "assists", FORWARD) is None


def test_saving_the_same_scope_twice_replaces_it(store):
    store.save(prior(FORWARD, alpha=5.0))
    store.save(prior(FORWARD, alpha=9.0))
    assert store.get("player", "goals", FORWARD).params["alpha"] == 9.0
    assert store.list_scopes("player", "goals") == [FORWARD]


def test_scope_key_order_does_not_matter(store):
    scope = {"position_general": "Forward", "season_name": "2024/25"}
    store.save(prior(scope))
    assert store.get("player", "goals", {"season_name": "2024/25", "position_general": "Forward"})


def test_list_scopes_covers_one_stat_most_specific_first(store):
    store.save(prior({}))
    store.save(prior(FORWARD))
    store.save(prior({"position_general": "Forward", "season_name": "2024/25"}))
    store.save(prior({}, stat_id="assists"))

    assert store.list_scopes("player", "goals") == [
        {"position_general": "Forward", "season_name": "2024/25"},
        FORWARD,
        {},
    ]
    assert store.list_scopes("player", "assists") == [{}]
    assert store.list_scopes("player", "shots") == []


def test_json_store_survives_being_reopened(tmp_path):
    path = tmp_path / "priors.json"
    JsonPriorStore(path).save(prior(FORWARD))
    assert JsonPriorStore(path).get("player", "goals", FORWARD).params["alpha"] == 5.0


def test_json_store_treats_a_missing_file_as_empty(tmp_path):
    assert JsonPriorStore(tmp_path / "nothing.json").list_scopes("player", "goals") == []


def test_json_store_creates_the_directory_it_writes_into(tmp_path):
    store = JsonPriorStore(tmp_path / "nested" / "priors.json")
    store.save(prior(FORWARD))
    assert (tmp_path / "nested" / "priors.json").exists()


def test_two_entity_types_share_a_stat_without_colliding(store):
    player = prior({}, alpha=5.0)
    club = prior({}, alpha=9.0).model_copy(update={"entity_type": "club"})
    store.save(player)
    store.save(club)

    assert store.get("player", "goals", {}).params["alpha"] == 5.0
    assert store.get("club", "goals", {}).params["alpha"] == 9.0
    assert store.list_scopes("player", "goals") == [{}]
    assert store.list_scopes("club", "goals") == [{}]


def test_the_written_file_is_versioned_and_holds_a_list_of_priors(tmp_path):
    path = tmp_path / "priors.json"
    JsonPriorStore(path).save(prior(FORWARD))

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == PRIOR_STORE_SCHEMA_VERSION
    assert [p["scope"] for p in payload["priors"]] == [FORWARD]


def test_a_stored_prior_carries_what_it_is_keyed_by(tmp_path):
    """The lookup key is rebuilt on load, so it is not written down and cannot go stale."""
    path = tmp_path / "priors.json"
    JsonPriorStore(path).save(prior(FORWARD))

    stored = json.loads(path.read_text(encoding="utf-8"))["priors"][0]

    assert (stored["entity_type"], stored["stat_id"], stored["scope"]) == (
        "player",
        "goals",
        FORWARD,
    )


def test_a_file_from_a_later_version_is_refused(tmp_path):
    path = tmp_path / "priors.json"
    path.write_text(json.dumps({"schema_version": 99, "priors": []}), encoding="utf-8")

    with pytest.raises(UnreadablePriorStore, match="version 99"):
        JsonPriorStore(path)


def test_an_unversioned_file_is_refused_rather_than_read(tmp_path):
    """The shape written before versioning: priors under encoded keys, no version."""
    path = tmp_path / "priors.json"
    path.write_text(
        json.dumps({'["player","goals",[]]': prior({}).model_dump()}), encoding="utf-8"
    )

    with pytest.raises(UnreadablePriorStore, match="version 0"):
        JsonPriorStore(path)
