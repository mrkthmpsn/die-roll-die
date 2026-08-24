from __future__ import annotations

import pytest

from die_scouting.csv_adapter import CsvDataAdapter

CSV = """\
player_source_id,player_name,season_name,position,position_general,nineties,goals,total_xg
1,Alice Adeyemi,2023/24,Forward,Forward,10,5,
1,Alice Adeyemi,2024/25,Forward,Forward,20,8,
2,Bo Bergstrom,2023/24,Centre Back,Defender,30,1,
3,Cara Costa,2023/24,Winger,Midfielder,0,4,
4,Dev Dhillon,2024/25,,Midfielder,5,,
"""


@pytest.fixture
def adapter(tmp_path):
    path = tmp_path / "player_seasons.csv"
    path.write_text(CSV, encoding="utf-8")
    return CsvDataAdapter(path)


def test_entity_observations_are_limited_to_that_entity(adapter):
    records = adapter.get_entity_observations("1", "goals")
    assert [r.entity_id for r in records] == ["1", "1"]
    assert [(r.value, r.denominator) for r in records] == [(5.0, 10.0), (8.0, 20.0)]


def test_records_carry_context_columns(adapter):
    record = adapter.get_entity_observations("2", "goals")[0]
    assert record.context["player_name"] == "Bo Bergstrom"
    assert record.context["season_name"] == "2023/24"
    assert record.context["position_general"] == "Defender"


def test_population_observations_span_entities(adapter):
    records = adapter.get_population_observations("goals")
    assert sorted(r.entity_id for r in records) == ["1", "1", "2"]


def test_scope_filters_by_column_value(adapter):
    records = adapter.get_population_observations("goals", {"position_general": "Forward"})
    assert {r.entity_id for r in records} == {"1"}


def test_scope_dimensions_compose(adapter):
    scope = {"position_general": "Forward", "season_name": "2024/25"}
    records = adapter.get_population_observations("goals", scope)
    assert [r.value for r in records] == [8.0]


def test_zero_denominator_rows_are_dropped(adapter):
    assert not adapter.get_entity_observations("3", "goals")


def test_blank_stat_values_are_skipped(adapter):
    assert not adapter.get_entity_observations("4", "goals")


def test_all_blank_columns_are_not_numeric(adapter):
    assert "total_xg" not in adapter.numeric_columns
    assert "goals" in adapter.numeric_columns


def test_entity_ids_for_name_matches_case_insensitively(adapter):
    assert adapter.entity_ids_for_name("alice") == ["1"]
    assert adapter.entity_ids_for_name("Nobody") == []


def test_unknown_stat_is_rejected(adapter):
    with pytest.raises(ValueError, match="total_xg"):
        adapter.get_population_observations("total_xg")


def test_unknown_scope_key_is_rejected(adapter):
    with pytest.raises(ValueError, match="team_name"):
        adapter.get_population_observations("goals", {"team_name": "Anywhere"})


def test_unknown_denominator_column_is_rejected(tmp_path):
    path = tmp_path / "player_seasons.csv"
    path.write_text(CSV, encoding="utf-8")
    with pytest.raises(ValueError, match="minutes"):
        CsvDataAdapter(path, denominator_column="minutes")
