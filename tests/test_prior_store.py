from __future__ import annotations

import pytest

from die_scouting import InMemoryPriorStore, JsonPriorStore, PriorParams

FORWARD = {"position_general": "Forward"}


def prior(scope: dict[str, str], alpha: float = 5.0, stat_id: str = "goals") -> PriorParams:
    return PriorParams(
        stat_id=stat_id, scope=scope, family="gamma", params={"alpha": alpha, "beta": 16.0}
    )


@pytest.fixture(params=["memory", "json"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryPriorStore()
    return JsonPriorStore(tmp_path / "priors.json")


def test_a_saved_prior_comes_back(store):
    store.save(prior(FORWARD))
    assert store.get("goals", FORWARD).params["alpha"] == 5.0


def test_an_unsaved_scope_is_a_miss(store):
    store.save(prior(FORWARD))
    assert store.get("goals", {"position_general": "Defender"}) is None
    assert store.get("assists", FORWARD) is None


def test_saving_the_same_scope_twice_replaces_it(store):
    store.save(prior(FORWARD, alpha=5.0))
    store.save(prior(FORWARD, alpha=9.0))
    assert store.get("goals", FORWARD).params["alpha"] == 9.0
    assert store.list_scopes("goals") == [FORWARD]


def test_scope_key_order_does_not_matter(store):
    scope = {"position_general": "Forward", "season_name": "2024/25"}
    store.save(prior(scope))
    assert store.get("goals", {"season_name": "2024/25", "position_general": "Forward"})


def test_list_scopes_covers_one_stat_most_specific_first(store):
    store.save(prior({}))
    store.save(prior(FORWARD))
    store.save(prior({"position_general": "Forward", "season_name": "2024/25"}))
    store.save(prior({}, stat_id="assists"))

    assert store.list_scopes("goals") == [
        {"position_general": "Forward", "season_name": "2024/25"},
        FORWARD,
        {},
    ]
    assert store.list_scopes("assists") == [{}]
    assert store.list_scopes("shots") == []


def test_json_store_survives_being_reopened(tmp_path):
    path = tmp_path / "priors.json"
    JsonPriorStore(path).save(prior(FORWARD))
    assert JsonPriorStore(path).get("goals", FORWARD).params["alpha"] == 5.0


def test_json_store_treats_a_missing_file_as_empty(tmp_path):
    assert JsonPriorStore(tmp_path / "nothing.json").list_scopes("goals") == []


def test_json_store_creates_the_directory_it_writes_into(tmp_path):
    store = JsonPriorStore(tmp_path / "nested" / "priors.json")
    store.save(prior(FORWARD))
    assert (tmp_path / "nested" / "priors.json").exists()
