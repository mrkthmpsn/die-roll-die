from __future__ import annotations

import pytest

from die_scouting import InMemoryPriorStore, Record, UnsuitableFamily, fit_scopes, scopes_for


class FakeAdapter:
    """Serves a fixed list of Records, filtering by scope on each Record's context."""

    def __init__(self, records: list[Record]) -> None:
        self.records = records

    def get_entity_observations(self, entity_id, stat_id, scope=None):
        return [r for r in self._matching(scope) if r.entity_id == entity_id]

    def get_population_observations(self, stat_id, scope=None):
        return self._matching(scope)

    def _matching(self, scope):
        scope = scope or {}
        return [
            r for r in self.records if all(r.context.get(k) == v for k, v in scope.items())
        ]


def season(entity_id: str, goals: float, nineties: float, position: str) -> Record:
    return Record(
        entity_id=entity_id,
        value=goals,
        denominator=nineties,
        context={"position_general": position},
    )


@pytest.fixture
def adapter():
    return FakeAdapter(
        [season(f"fwd-{i}", 8 + i, 20 + i, "Forward") for i in range(12)]
        + [season(f"def-{i}", 1 + i, 25 + i, "Defender") for i in range(12)]
        + [season("gk-1", 0, 30, "Goalkeeper")]
    )


def test_scopes_for_returns_one_scope_per_distinct_value(adapter):
    assert scopes_for(adapter, "goals", "position_general") == [
        {"position_general": "Defender"},
        {"position_general": "Forward"},
        {"position_general": "Goalkeeper"},
    ]


def test_scopes_for_ignores_records_without_the_column():
    adapter = FakeAdapter(
        [season("fwd-1", 8, 20, "Forward"), Record(entity_id="x", value=1, denominator=2)]
    )
    assert scopes_for(adapter, "goals", "position_general") == [
        {"position_general": "Forward"}
    ]


def test_scopes_for_rejects_a_column_nothing_carries(adapter):
    with pytest.raises(ValueError, match="team_name"):
        scopes_for(adapter, "goals", "team_name")


def test_fit_scopes_saves_what_it_fits(adapter):
    store = InMemoryPriorStore()
    scopes = [{}] + scopes_for(adapter, "goals", "position_general")

    report = fit_scopes(adapter, store, "goals", "gamma", scopes)

    assert {} in report.fitted
    assert {"position_general": "Forward"} in report.fitted
    assert store.get("goals", {"position_general": "Forward"}) is not None


def test_fit_scopes_skips_a_scope_with_too_little_data(adapter):
    store = InMemoryPriorStore()
    scopes = scopes_for(adapter, "goals", "position_general")

    report = fit_scopes(adapter, store, "goals", "gamma", scopes)

    skipped_scopes = [scope for scope, _ in report.skipped]
    assert {"position_general": "Goalkeeper"} in skipped_scopes
    assert store.get("goals", {"position_general": "Goalkeeper"}) is None
    assert "at least two observations" in dict(
        (tuple(sorted(s.items())), reason) for s, reason in report.skipped
    )[(("position_general", "Goalkeeper"),)]


def test_fit_scopes_does_not_swallow_a_wrong_family():
    """A beta needs successes counted out of attempts, and these values exceed theirs."""
    adapter = FakeAdapter([season(f"fwd-{i}", 40 + i, 20 + i, "Forward") for i in range(12)])

    with pytest.raises(UnsuitableFamily):
        fit_scopes(adapter, InMemoryPriorStore(), "goals", "beta", [{}])
