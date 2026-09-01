from __future__ import annotations

import pytest

from die_roll_die.csv_adapter import ColumnMap, CsvDataAdapter

CSV = """\
player_source_id,player_name,season_name,position,position_general,appearances,goals,total_xg
1,Alice Adeyemi,2023/24,Forward,Forward,10,5,
1,Alice Adeyemi,2024/25,Forward,Forward,20,8,
2,Bo Bergstrom,2023/24,Centre Back,Defender,30,1,
3,Cara Costa,2023/24,Winger,Midfielder,0,4,
4,Dev Dhillon,2024/25,,Midfielder,5,,
"""


CLEAN_CSV = """id,games,tries
7,12,4
7,9,2
"""

KEEPERS_CSV = """id,minutes,saves
1,90,
2,0,5
3,,4
"""

COLUMNS = ColumnMap(
    entity="player_source_id",
    entity_type="player",
    denominator="appearances",
    name="player_name",
    dimensions=("player_name", "season_name", "position", "position_general"),
)


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "player_seasons.csv"
    path.write_text(CSV, encoding="utf-8")
    return path


@pytest.fixture
def adapter(csv_path):
    return CsvDataAdapter(csv_path, COLUMNS)


def test_entity_observations_are_limited_to_that_entity(adapter):
    records = adapter.get_entity_observations("1", "goals")
    assert [r.entity_id for r in records] == ["1", "1"]
    assert [(r.value, r.denominator) for r in records] == [(5.0, 10.0), (8.0, 20.0)]


def test_records_carry_dimensions(adapter):
    record = adapter.get_entity_observations("2", "goals")[0]
    assert record.dimensions["player_name"] == "Bo Bergstrom"
    assert record.dimensions["season_name"] == "2023/24"
    assert record.dimensions["position_general"] == "Defender"


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


def test_a_column_holding_no_number_says_so(adapter):
    """`total_xg` is in the header and blank in every row, so it is not a numeric column —
    which is a different thing from not being a column at all.
    """
    with pytest.raises(ValueError, match="total_xg' is a column of the file but no row kept"):
        adapter.get_population_observations("total_xg")


def test_a_stat_absent_from_the_header_says_that_instead(adapter):
    with pytest.raises(ValueError, match="'minutes' is not a column of the file"):
        adapter.get_population_observations("minutes")


def test_dropped_rows_counts_what_the_denominator_filter_removed(adapter):
    """Cara Costa's row has `appearances` of 0."""
    assert adapter.dropped_rows == 1


def test_dropped_rows_is_zero_for_a_file_that_passes_whole(tmp_path):
    path = tmp_path / "clean.csv"
    path.write_text(CLEAN_CSV, encoding="utf-8")
    adapter = CsvDataAdapter(
        path, ColumnMap(entity="id", entity_type="player", denominator="games")
    )
    assert adapter.dropped_rows == 0


def test_the_message_names_the_filter_when_it_removed_the_rows(tmp_path):
    """`saves` holds a number in two rows the filter drops and in none it keeps, so the
    count is what points at why the column looks empty.
    """
    path = tmp_path / "keepers.csv"
    path.write_text(KEEPERS_CSV, encoding="utf-8")
    adapter = CsvDataAdapter(
        path, ColumnMap(entity="id", entity_type="player", denominator="minutes")
    )
    with pytest.raises(ValueError, match="2 rows were dropped"):
        adapter.get_population_observations("saves")


def test_unknown_scope_key_is_rejected(adapter):
    with pytest.raises(ValueError, match="team_name"):
        adapter.get_population_observations("goals", {"team_name": "Anywhere"})


def test_unknown_denominator_column_is_rejected(csv_path):
    with pytest.raises(ValueError, match="minutes"):
        CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"denominator": "minutes"}))


def test_unknown_entity_column_is_rejected(csv_path):
    with pytest.raises(ValueError, match="entity column 'player_id'"):
        CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"entity": "player_id"}))


def test_unknown_name_column_is_rejected(csv_path):
    with pytest.raises(ValueError, match="name column 'full_name'"):
        CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"name": "full_name"}))


def test_unknown_dimension_column_is_rejected(csv_path):
    with pytest.raises(ValueError, match="team_name"):
        CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"dimensions": ("team_name",)}))


def test_columns_can_be_named_anything(tmp_path):
    path = tmp_path / "other.csv"
    path.write_text(
        "id,full_name,games,tries\n7,Ada Lovelace,12,4\n7,Ada Lovelace,9,2\n",
        encoding="utf-8",
    )
    adapter = CsvDataAdapter(
        path, ColumnMap(entity="id", entity_type="player", denominator="games", name="full_name")
    )

    assert adapter.entity_ids_for_name("ada") == ["7"]
    records = adapter.get_entity_observations("7", "tries")
    assert [(r.value, r.denominator) for r in records] == [(4.0, 12.0), (2.0, 9.0)]


def test_a_map_without_a_name_column_cannot_search_names(csv_path):
    adapter = CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"name": None}))
    with pytest.raises(ValueError, match="no `name` column"):
        adapter.entity_ids_for_name("Alice")


def test_dimensions_carry_exactly_the_mapped_columns(csv_path):
    columns = COLUMNS.model_copy(update={"dimensions": ("season_name",)})
    record = CsvDataAdapter(csv_path, columns).get_entity_observations("1", "goals")[0]
    assert record.dimensions == {"season_name": "2023/24"}


def test_any_column_can_be_the_denominator(tmp_path):
    path = tmp_path / "player_seasons.csv"
    path.write_text(CSV, encoding="utf-8")
    adapter = CsvDataAdapter(path, COLUMNS.model_copy(update={"denominator": "goals"}))
    record = adapter.get_entity_observations("2", "appearances")[0]
    assert (record.value, record.denominator) == (30.0, 1.0)


def test_records_carry_the_entity_type(adapter):
    record = adapter.get_entity_observations("1", "goals")[0]
    assert record.entity_type == "player"


def test_entity_name_resolves_an_id(adapter):
    assert adapter.entity_name("1") == "Alice Adeyemi"


def test_entity_name_is_none_for_an_unknown_id(adapter):
    assert adapter.entity_name("nobody") is None


def test_entity_name_needs_a_mapped_name_column(csv_path):
    adapter = CsvDataAdapter(csv_path, COLUMNS.model_copy(update={"name": None}))
    with pytest.raises(ValueError, match="no `name` column"):
        adapter.entity_name("1")
