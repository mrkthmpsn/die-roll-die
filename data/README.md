# data

Licensed CC BY-SA 4.0, unlike the rest of the repository — see [LICENSE](LICENSE) for why and
for the attribution these files carry.

## `player_seasons.csv`

Premier League player-season aggregates for the five seasons 2021/22 to 2025/26, one row per
player per season per club. A player transferred mid-season has a row for each club, which is
two observations of the same entity rather than one averaged over both.

Built by [`tools/wikipedia_squads.py`](../tools/wikipedia_squads.py) from the squad statistics
tables of English Wikipedia's club-season articles; run it again to rebuild the file. Every
source article is listed in [`sources.json`](sources.json) with the revision id its figures were
read from.

### Columns

| Column | Note |
| --- | --- |
| `provider` | `wikipedia` throughout |
| `player_source_id` | The player's Wikipedia page title, used as `Record.entity_id`; stable where the display name varies between articles |
| `player_name`, `club_name` | As the article writes them |
| `competition_name`, `season_name` | `Premier League` throughout; season as `2024/25` |
| `position_general` | `Goalkeeper` / `Defender` / `Midfielder` / `Forward`, from the article's one- or two-letter position |
| `appearances` | Starts plus substitute appearances |
| `starts`, `sub_appearances` | Populated on 2,534 of 2,753 rows; see below |
| `goals` | |

`appearances` is the denominator `CsvDataAdapter` reads by default. It is coarser than the
minutes a per-90 rate would want — a five-minute substitute appearance counts the same as
ninety — because Wikipedia records minutes on almost no club-season article.

Nothing in the file carries assists, shots, expected goals, or a finer position than the four
groups, all of which the source lacks.

### `starts` and `sub_appearances`

Articles record the split three ways, and all three are read: a cell written `35+2` or `35 (2)`;
a competition given an appearances column and a starts column, where the substitutions are the
difference; and a competition given a starts column and a substitutes column, where the
appearances are the sum.

Within a table that writes the split at all, a bare count is read as all starts and no
substitute appearances, because an editor using the notation writes `0+12` for a player who
only came off the bench. Goalkeepers are 7% of the rows and were 39% of the bare counts, which
is the shape that reading predicts.

Both columns are blank for the 219 rows from nine club-seasons — Chelsea in three, Manchester
City in five, Luton in 2023/24 — whose tables give a total and nothing about how it divided.
Blank there means unknown rather than zero, so a denominator of `starts` silently covers fewer
players than one of `appearances`.

### What is not here

Rows whose per-competition figures did not sum to the article's own stated total were dropped
rather than shipped, so every row here is internally consistent. That is a real cost in a few
places: Manchester City's 2023/24 article states totals that disagree with its own columns for
twelve players, so those twelve are absent even though their league figures look right.

Where a club's article carried no goals table at all, its players are absent rather than
recorded with zero goals, since an absent goals table is unknown and absence from an existing
one is nil.

### Rebuilding

```
uv run --group scrape python tools/wikipedia_squads.py
```

The scraper checks itself: it fails when it parses too few articles or reconciles too few rows,
because the tables it reads are a convention among editors rather than a schema and will change
without notice. `LAYOUT_VERSION` in that module records the layouts it was written against.
