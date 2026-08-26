# data

Licensed CC BY-SA 4.0, unlike the rest of the repository — see [LICENSE](LICENSE) for why and
for the attribution these files carry.

## `player_seasons.csv`

Premier League player-season aggregates for the five seasons 2021/22 to 2025/26, one row per
player per season per club. A player transferred mid-season has a row for each club, which is
two observations of the same entity rather than one averaged over both.

Built by [`tools/wikipedia_squads.py`](../tools/wikipedia_squads.py) from the squad statistics
tables of English Wikipedia's club-season articles; run it again to rebuild the file. It reads the
twenty clubs of each season, 100 articles in all; [`sources.json`](sources.json) lists them with
the revision id each was read at and what each contributed.

### Columns

| Column | Note |
| --- | --- |
| `provider` | `wikipedia` throughout |
| `player_source_id` | The player's Wikipedia page title, used as `Record.entity_id`; stable where the display name varies between articles |
| `player_name`, `club_name` | As the article writes them |
| `competition_name`, `season_name` | `Premier League` throughout; season as `2024/25` |
| `position_general` | `Goalkeeper` / `Defender` / `Midfielder` / `Forward`, from the article's one- or two-letter position |
| `appearances` | Starts plus substitute appearances |
| `goals` | |

`appearances` is the denominator `CsvDataAdapter` reads by default, and is above zero on every row. It is coarser than the
minutes a per-90 rate would want — a five-minute substitute appearance counts the same as
ninety — because Wikipedia records minutes on almost no club-season article.

Nothing in the file carries assists, shots, expected goals, or a finer position than the four
groups, all of which the source lacks.

### Why there is no starts column

Articles record the starts-and-substitutes split three ways and the scraper reads all three — a
cell written `35+2` or `35 (2)`, a competition given appearances and starts, and a competition
given starts and substitutes — because several layouts give the appearance count only as the sum
of the other two. None of it is written out.

Nine club-seasons record no split at all: Chelsea in three seasons, Manchester City in five,
Luton in 2023/24. A denominator available for eleven clubs and missing for nine would quietly
change which players an estimate covers depending on who they played for, which is worse than
not offering it. `appearances` is populated on every row.

### Who is not here

A player needs at least one Premier League appearance to get a row, so 565 of the 3,369 squad
members read from these articles are absent: those who played only in the cups or in Europe, and
named substitutes who never got on. `CsvDataAdapter` drops rows with a zero denominator when it
reads the file anyway, on the grounds that a count over no exposure is not a rate, so those rows
would be discarded the moment they were used. `sources.json` records both counts per article,
the largest gap being Chelsea's 2024/25 squad of 65 yielding 29 rows.

The consequence is that this file is not a squad list. Nothing in it records that a player was
at a club without featuring, and playing time is not modelled, so there is nowhere for that fact
to sit.

### What is not here

57 of the 2,804 rows come from articles whose per-competition figures do not sum to the total
they state, most of them Manchester City's, whose grid carries twenty-four numeric columns per
player and is the hardest on the site to keep consistent by hand. Those rows are kept, because
the disagreement is in cup and European columns that never reach this file while the Premier
League figure they carry is right. `sources.json` records the count per article.

What is dropped is a whole table whose rows mostly fail that check, since a table where half the
rows do not add up has been read out of alignment rather than typed wrong. No table in the
current build fell to that.

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
