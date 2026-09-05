"""Fixtures here are written by hand in the shape of the real articles rather than saved from
Wikipedia, so that no CC BY-SA content enters `tests/`."""

from __future__ import annotations

from bs4 import BeautifulSoup

from tools.wikipedia_squads import (
    Entry,
    USER_AGENT,
    league_rows,
    merge,
    parse_table,
    reconcile,
    _headings_for,
)


def test_the_user_agent_names_the_repository():
    """Wikimedia's User-Agent policy asks for a URL its operators can make contact through,
    which a bare host is not."""
    assert "github.com/mrkthmpsn/die-roll-die" in USER_AGENT

COMBINED = """
<h2>Statistics</h2><h3>Appearances and goals</h3>
<table class="wikitable">
<tr><th rowspan="2">No.</th><th rowspan="2">Pos.</th><th rowspan="2">Player</th>
    <th colspan="2">Premier League</th><th colspan="2">FA Cup</th><th colspan="2">Total</th></tr>
<tr><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th></tr>
<tr><td>7</td><td>FW</td><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>30</td><td>12</td><td>2</td><td>1</td><td>32</td><td>13</td></tr>
<tr><td>4</td><td>MF</td><td><a href="/wiki/Bo_Baker">Bo Baker</a></td>
    <td>25+3</td><td>4</td><td>1</td><td>0</td><td>29</td><td>4</td></tr>
</table>
"""

ICON_GRID = """
<h2>Statistics</h2><h3>Overall</h3>
<table class="wikitable">
<tr><th rowspan="2">No.</th><th rowspan="2">Player</th><th rowspan="2">Pos.</th>
    <th colspan="4">Premier League</th><th colspan="4">Total</th></tr>
<tr><th><img alt="&#128085;"/></th><th><abbr title="Goal"></abbr></th>
    <th><abbr title="Booked"><img alt="Yellow card"/></abbr></th>
    <th><abbr title="Sent off (straight red)"><img alt="Red card"/></abbr></th>
    <th><img alt="&#128085;"/></th><th><abbr title="Goal"></abbr></th>
    <th><abbr title="Booked"><img alt="Yellow card"/></abbr></th>
    <th><abbr title="Sent off (straight red)"><img alt="Red card"/></abbr></th></tr>
<tr><td>9</td><td><a href="/wiki/Cy_Cole">Cy Cole</a></td><td>FW</td>
    <td>31</td><td>27</td><td>3</td><td></td>
    <td>31</td><td>27</td><td>3</td><td></td></tr>
</table>
"""

SPLIT = """
<h2>Statistics</h2><h3>Appearances</h3>
<table class="wikitable">
<tr><th>No.</th><th>Pos.</th><th>Player</th><th>Premier League</th><th>FA Cup</th><th>Total</th></tr>
<tr><td>7</td><td>FW</td><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>30</td><td>2</td><td>32</td></tr>
<tr><td>4</td><td>MF</td><td><a href="/wiki/Bo_Baker">Bo Baker</a></td>
    <td>28</td><td>1</td><td>29</td></tr>
</table>
<h3>Goals</h3>
<table class="wikitable">
<tr><th>Rank</th><th>No.</th><th>Pos.</th><th>Player</th>
    <th>Premier League</th><th>FA Cup</th><th>Total</th></tr>
<tr><td>1</td><td>7</td><td>FW</td><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>12</td><td>1</td><td>13</td></tr>
</table>
"""

SQUAD = """
<h2>First-team squad</h2>
<table class="wikitable">
<tr><th>No.</th><th>Player</th><th>Pos.</th><th>App</th><th>Goals</th></tr>
<tr><td>2</td><td><a href="/wiki/Di_Dane">Di Dane</a></td><td>DF</td><td>215</td><td>6</td></tr>
</table>
"""

UNRECONCILED = """
<h2>Statistics</h2><h3>Appearances and goals</h3>
<table class="wikitable">
<tr><th rowspan="2">Player</th><th colspan="2">Premier League</th>
    <th colspan="2">FA Cup</th><th colspan="2">Total</th></tr>
<tr><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th></tr>
<tr><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>30</td><td>12</td><td>2</td><td>1</td><td>32</td><td>13</td></tr>
<tr><td><a href="/wiki/Bo_Baker">Bo Baker</a></td>
    <td>25</td><td>4</td><td>1</td><td>0</td><td>99</td><td>4</td></tr>
</table>
"""


def tables(html: str):
    """Every wikitable in the fragment, parsed with its own headings."""
    soup = BeautifulSoup(html, "lxml")
    found = []
    for table in soup.find_all("table", class_="wikitable"):
        result = parse_table(table, _headings_for(table))
        if result is not None:
            found.append(result)
    return found


def by_name(entries: list[Entry]) -> dict[str, Entry]:
    return {entry.player_name: entry for entry in entries}


def test_combined_table_reads_both_metrics():
    (parsed,) = tables(COMBINED)
    assert parsed.metrics == {"apps", "goals"}
    ada = by_name(parsed.entries)["Ada Ames"]
    assert ada.values[("Premier League", "apps")] == 30
    assert ada.values[("Premier League", "goals")] == 12
    assert ada.values[("FA Cup", "apps")] == 2
    assert ada.position == "Forward"


def test_starts_and_substitute_appearances_split_out():
    (parsed,) = tables(COMBINED)
    bo = by_name(parsed.entries)["Bo Baker"]
    assert bo.values[("Premier League", "apps")] == 28
    assert bo.values[("Premier League", "starts")] == 25
    assert bo.values[("Premier League", "sub_appearances")] == 3


def test_icon_headers_are_read_and_card_columns_ignored():
    """Appearances headed by a shirt image and goals by an abbreviation both read as empty
    text, and the two card columns must not be mistaken for metrics."""
    (parsed,) = tables(ICON_GRID)
    cy = by_name(parsed.entries)["Cy Cole"]
    assert cy.values[("Premier League", "apps")] == 31
    assert cy.values[("Premier League", "goals")] == 27
    assert parsed.metrics == {"apps", "goals"}
    assert not [key for key in cy.values if key[1] not in ("apps", "goals")]


def test_table_under_an_unknown_heading_is_still_parsed():
    """`Overall` is in no vocabulary of section names; the table is found by its headers."""
    assert tables(ICON_GRID)


def test_split_tables_merge_to_the_combined_result():
    parsed = tables(SPLIT)
    assert len(parsed) == 2
    entries, supplied, conflicts = merge(parsed)
    assert not conflicts
    assert supplied == {"apps", "goals"}
    ada = by_name(entries)["Ada Ames"]
    assert ada.values[("Premier League", "apps")] == 30
    assert ada.values[("Premier League", "goals")] == 12


def test_a_squad_member_absent_from_the_goals_table_scores_zero():
    entries, supplied, _ = merge(tables(SPLIT))
    rows = {row["player_name"]: row for row in league_rows(entries, supplied)}
    assert rows["Bo Baker"]["goals"] == 0
    assert rows["Bo Baker"]["appearances"] == 28


def test_players_are_dropped_when_no_table_supplied_goals():
    """Absence of a goals table is unknown rather than zero, unlike absence from one."""
    appearances_only = [parsed for parsed in tables(SPLIT) if parsed.metrics == {"apps"}]
    entries, supplied, _ = merge(appearances_only)
    assert supplied == {"apps"}
    assert league_rows(entries, supplied) == []


def test_squad_tables_are_excluded_as_career_totals():
    assert tables(SQUAD) == []


def test_rows_failing_their_own_total_are_rejected():
    (parsed,) = tables(UNRECONCILED)
    kept, rejected = reconcile(parsed.entries)
    assert by_name(kept).keys() == {"Ada Ames"}
    assert [entry.player_name for entry, _ in rejected] == ["Bo Baker"]
    assert rejected[0][1] == "apps"


def test_conflicting_tables_reject_the_player():
    parsed = tables(SPLIT)
    parsed[1].entries[0].values[("Premier League", "apps")] = 99
    entries, _, conflicts = merge(parsed)
    assert [entry.player_name for entry, _ in conflicts] == ["Ada Ames"]
    assert "Ada Ames" not in by_name(entries)


BRACKETED_SUBS = """
<h2>Statistics</h2><h3>Appearances and goals</h3>
<table class="wikitable">
<tr><th rowspan="2">Player</th><th colspan="2">Premier League</th><th colspan="2">Total</th></tr>
<tr><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th></tr>
<tr><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>9 (1)</td><td>2</td><td>9 (1)</td><td>2</td></tr>
</table>
"""

INDEX_COLUMNS = """
<h2>Statistics</h2><h3>Goalscorers</h3>
<table class="wikitable">
<tr><th>Rank</th><th>No</th><th>Pos</th><th>Nat</th><th>Player</th>
    <th>Premier League</th><th>Total</th></tr>
<tr><td>1</td><td>9</td><td>FW</td><td>ENG</td>
    <td><a href="/wiki/Ada_Ames">Ada Ames</a></td><td>12</td><td>12</td></tr>
</table>
"""


def test_substitute_appearances_in_brackets():
    """`9 (1)` and `25+3` are both in use for starts plus substitute appearances."""
    (parsed,) = tables(BRACKETED_SUBS)
    ada = by_name(parsed.entries)["Ada Ames"]
    assert ada.values[("Premier League", "apps")] == 10
    assert ada.values[("Premier League", "starts")] == 9
    assert ada.values[("Premier League", "sub_appearances")] == 1


MIXED_NOTATION = """
<h2>Statistics</h2><h3>Appearances and goals</h3>
<table class="wikitable">
<tr><th rowspan="2">Player</th><th colspan="2">Premier League</th><th colspan="2">Total</th></tr>
<tr><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th></tr>
<tr><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>25+3</td><td>4</td><td>25+3</td><td>4</td></tr>
<tr><td><a href="/wiki/Bo_Baker">Bo Baker</a></td>
    <td>38</td><td>0</td><td>38</td><td>0</td></tr>
</table>
"""


APPS_AND_STARTS = """
<h2>Statistics</h2><h3>Appearances</h3>
<table class="wikitable">
<tr><th rowspan="2">Player</th><th colspan="2">Premier League</th><th>Total</th></tr>
<tr><th>Apps</th><th>Starts</th><th>Apps</th></tr>
<tr><td><a href="/wiki/Ada_Ames">Ada Ames</a></td><td>35</td><td>27</td><td>35</td></tr>
</table>
"""

STARTS_AND_SUBS = """
<h2>Statistics</h2><h3>Appearances, goals and cards</h3>
<table class="wikitable">
<tr><th rowspan="2">Player</th><th colspan="3">Premier League</th><th colspan="3">Total</th></tr>
<tr><th>Starts</th><th>Sub</th><th>Goals</th><th>Starts</th><th>Sub</th><th>Goals</th></tr>
<tr><td><a href="/wiki/Ada_Ames">Ada Ames</a></td>
    <td>27</td><td>8</td><td>5</td><td>27</td><td>8</td><td>5</td></tr>
</table>
"""


def test_substitutions_are_the_difference_when_only_apps_and_starts_are_given():
    """Liverpool and Aston Villa head each competition with appearances and starts and no
    substitutes column, so zeroing the substitutions would contradict the appearances."""
    (parsed,) = tables(APPS_AND_STARTS)
    ada = by_name(parsed.entries)["Ada Ames"]
    assert ada.values[("Premier League", "apps")] == 35
    assert ada.values[("Premier League", "starts")] == 27
    assert ada.values[("Premier League", "sub_appearances")] == 8


def test_appearances_are_the_sum_when_only_starts_and_subs_are_given():
    (parsed,) = tables(STARTS_AND_SUBS)
    ada = by_name(parsed.entries)["Ada Ames"]
    assert ada.values[("Premier League", "apps")] == 35
    assert ada.values[("Premier League", "sub_appearances")] == 8
    assert ada.values[("Premier League", "goals")] == 5


def test_a_plain_count_is_all_starts_where_the_table_writes_the_split():
    """An editor using `25+3` would have written `0+38` for a substitute, so a bare 38 in the
    same table is a player who never came off the bench."""
    (parsed,) = tables(MIXED_NOTATION)
    bo = by_name(parsed.entries)["Bo Baker"]
    assert bo.values[("Premier League", "starts")] == 38
    assert bo.values[("Premier League", "sub_appearances")] == 0


def test_a_plain_count_stays_unknown_where_the_table_never_writes_the_split():
    appearances = next(parsed for parsed in tables(SPLIT) if parsed.metrics == {"apps"})
    ada = by_name(appearances.entries)["Ada Ames"]
    assert ("Premier League", "starts") not in ada.values


def test_dotless_index_columns_are_not_competitions():
    """A column headed `No` is a squad number; read as a competition it would put the shirt
    number where a goal count belongs, and the row would then fail its own total."""
    (parsed,) = tables(INDEX_COLUMNS)
    ada = by_name(parsed.entries)["Ada Ames"]
    assert sorted({competition for competition, _ in ada.values}) == ["Premier League", "Total"]
    kept, rejected = reconcile(parsed.entries)
    assert not rejected


def test_player_identity_is_the_page_title():
    (parsed,) = tables(COMBINED)
    assert {entry.player_key for entry in parsed.entries} == {"Ada_Ames", "Bo_Baker"}


def test_headings_include_the_parent_section():
    soup = BeautifulSoup(ICON_GRID, "lxml")
    table = soup.find("table", class_="wikitable")
    assert _headings_for(table) == ["Overall", "Statistics"]
