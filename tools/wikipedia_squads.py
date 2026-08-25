"""Build a player-season CSV from the squad statistics tables of Wikipedia club-season
articles.

Tables are found by what their headers resolve to rather than by the section they sit under:
any wikitable with a player column and at least one column resolving to an appearances or
goals metric is read. Section headings are consulted only to supply a metric the columns
leave implicit, and to exclude squad tables, whose appearance and goal figures are career
totals rather than the season's.

`LAYOUT_VERSION` records the article layouts this was written against; see the module
constants below for the header vocabulary and `--help` for the command line.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup, Tag

LAYOUT_VERSION = "2026-08-25"
"""The Wikipedia layouts this parser was verified against.

Handled: one table carrying both appearances and goals per competition; separate Appearances
and Goals tables merged on the player; a combined grid whose competitions each span
appearances, goals and two card columns; two-row headers where the competition spans a
`colspan` and the metric sits beneath; single-row headers whose columns are bare competition
names and whose metric comes from the section heading; cells written `35+2` for starts plus
substitute appearances. Verified against the twenty Premier League clubs for each of the
seasons 2021-22 to 2025-26.
"""

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "die-scouting/0.1 (https://github.com/; wikipedia squad statistics scraper)"
REQUEST_DELAY = 0.25

SEASONS = ("2021–22", "2022–23", "2023–24", "2024–25", "2025–26")

PLAYER_LABELS = ("player", "name")
APPS_LABELS = ("apps", "app", "appearances", "appearance", "\U0001f455")
GOALS_LABELS = ("goals", "goal", "gls", "⚽")
IGNORED_METRIC_LABELS = (
    "assists", "assist", "yellow card", "yellow cards", "red card", "red cards",
    "booked", "sent off", "sent off (straight red)", "second yellow", "clean sheets",
    "cs", "minutes", "mins", "starts", "sub", "subs",
)
IGNORED_COMPETITIONS = (
    "career club total", "career total", "career", "ref.", "ref", "reference(s)",
    "notes", "rank", "rk.", "rk", "rnk", "no.", "no", "pos.", "pos", "nat.", "nat",
    "player", "name", "#", "age", "since", "ends", "fee",
)
"""Column labels that are not competitions.

The dotless spellings matter: several clubs head their index columns `No`, `Pos` and `Nat`,
and a squad number read as a competition puts the shirt number where a goal count belongs.
"""
TOTAL_LABELS = ("total", "totals", "season total")
LEAGUE_LABELS = ("premier league", "league", "pl")
LEAGUE_NAME = "Premier League"

SQUAD_HEADING = re.compile(
    r"^(first[- ]team squad|squad|players|academy players|first[- ]team)$", re.I
)
"""Roster sections, whose appearance and goal columns are career totals.

Matched whole, because `Squad statistics` is a season table and excluding it on the word
`squad` alone loses a third of the clubs.
"""
APPS_HEADING = re.compile(r"appearance", re.I)
GOALS_HEADING = re.compile(r"goal", re.I)

POSITION_GROUPS = {
    "GK": "Goalkeeper",
    "DF": "Defender",
    "MF": "Midfielder",
    "FW": "Forward",
}

CELL_NUMBER = re.compile(r"^(\d+)(?:\s*(?:\+\s*(\d+)|\(\s*(\d+)\s*\)))?$")
"""A count, optionally with substitute appearances written `35+2` or `35 (2)`."""
FOOTNOTE = re.compile(r"\[\s*[a-z0-9]+\s*\]", re.I)


# --------------------------------------------------------------------------- parsing


@dataclass
class Entry:
    """One player's figures from one article, keyed by competition and metric."""

    player_key: str
    player_name: str
    position: str | None = None
    values: dict[tuple[str, str], int] = field(default_factory=dict)


@dataclass
class ParsedTable:
    """One table's entries and the metrics its header supplied."""

    entries: list[Entry]
    metrics: set[str]


def _norm(text: str) -> str:
    """Lower-case a header label, drop footnote markers, and collapse whitespace."""
    text = FOOTNOTE.sub(" ", unicodedata.normalize("NFKC", text))
    return re.sub(r"\s+", " ", text).strip().lower()


def _label(cell: Tag) -> str:
    """The cell's label: its text, or an `abbr`/`span` title, or an `img` alt.

    Manchester City heads appearances with a shirt emoji and goals with an abbreviation, so
    both read as empty text and neither is found without the fallbacks.
    """
    text = cell.get_text(" ", strip=True)
    if text:
        return text
    for node in cell.find_all(["abbr", "span"]):
        title = node.get("title")
        if title:
            return title
    image = cell.find("img")
    if image and image.get("alt"):
        return image["alt"]
    return ""


def _metric(label: str) -> str | None:
    """`apps`, `goals`, `ignore` for a known non-metric column, or None when unrecognised."""
    if label in APPS_LABELS:
        return "apps"
    if label in GOALS_LABELS:
        return "goals"
    if label in IGNORED_METRIC_LABELS:
        return "ignore"
    return None


def _competition(raw: str) -> str | None:
    """A competition's name as the article writes it, or None when the label names something
    else. `Total` and the several spellings of the league are given canonical names; every
    other label keeps its own casing, so `FA Cup` is not retitled."""
    cleaned = FOOTNOTE.sub(" ", unicodedata.normalize("NFKC", raw))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    key = cleaned.lower()
    if not cleaned or key in IGNORED_COMPETITIONS:
        return None
    if key in TOTAL_LABELS:
        return "Total"
    if key in LEAGUE_LABELS:
        return LEAGUE_NAME
    return cleaned


def _expand(rows: list[Tag]) -> list[dict[int, Tag]]:
    """Expand table rows into `{column index: cell}` per row, honouring colspan and rowspan."""
    grid: list[dict[int, Tag]] = []
    carried: dict[tuple[int, int], Tag] = {}
    for index, row in enumerate(rows):
        line: dict[int, Tag] = {}
        for (target, column), cell in list(carried.items()):
            if target == index:
                line[column] = cell
                del carried[(target, column)]
        column = 0
        for cell in row.find_all(["th", "td"], recursive=False):
            while column in line:
                column += 1
            span = int(cell.get("colspan") or 1)
            rows_spanned = int(cell.get("rowspan") or 1)
            for offset in range(span):
                line[column + offset] = cell
                for down in range(1, rows_spanned):
                    carried[(index + down, column + offset)] = cell
            column += span
        grid.append(line)
    return grid


def _resolve_header(
    header: list[dict[int, Tag]], section_metric: str | None
) -> tuple[dict[int, tuple[str, str]], int | None]:
    """Map each column to `(competition, metric)`, and find the player column.

    Where a column's lower header cell names a metric, the upper cell names its competition.
    Where the lower cell names a competition instead, or repeats the upper cell because it
    spans both rows, the metric comes from `section_metric`.
    """
    if not header:
        return {}, None
    top = header[0]
    bottom = header[1] if len(header) > 1 else {}
    mapping: dict[int, tuple[str, str]] = {}
    player_column: int | None = None

    for column in sorted(set(top) | set(bottom)):
        top_cell = top.get(column)
        bottom_cell = bottom.get(column)
        top_raw = _label(top_cell) if top_cell is not None else ""
        bottom_raw = _label(bottom_cell) if bottom_cell is not None else ""
        if top_cell is not None and bottom_cell is top_cell:
            bottom_raw = ""
        top_label, bottom_label = _norm(top_raw), _norm(bottom_raw)

        if top_label in PLAYER_LABELS or bottom_label in PLAYER_LABELS:
            player_column = column
            continue

        metric = _metric(bottom_label)
        if metric is not None:
            competition = _competition(top_raw)
        else:
            metric = section_metric
            competition = _competition(bottom_raw or top_raw)
        if metric is None or metric == "ignore" or competition is None:
            continue
        mapping[column] = (competition, metric)

    return mapping, player_column


def _identity(cell: Tag) -> tuple[str, str] | None:
    """The player's page title and display name, from the longest article link in the cell."""
    best: Tag | None = None
    for link in cell.find_all("a", href=True):
        href = link["href"]
        if not href.startswith("/wiki/") or ":" in href[6:]:
            continue
        if best is None or len(link.get_text(strip=True)) > len(best.get_text(strip=True)):
            best = link
    if best is None or not best.get_text(strip=True):
        return None
    return unquote(best["href"][len("/wiki/"):]), best.get_text(" ", strip=True)


def _number(text: str) -> tuple[int, int | None, int | None] | None:
    """`(appearances, starts, substitute appearances)` from a cell, or None when it is blank.

    A cell written `35+2` or `35 (2)` is thirty-five starts and two substitute appearances,
    both spellings being in use; a plain integer leaves the split unknown; a dash or an empty
    cell is did-not-compete.
    """
    cleaned = FOOTNOTE.sub("", text).strip()
    cleaned = cleaned.replace("–", "").replace("—", "").strip()
    if not cleaned:
        return None
    match = CELL_NUMBER.match(cleaned.replace(",", ""))
    if match is None:
        return None
    starts = int(match.group(1))
    subs_text = match.group(2) or match.group(3)
    subs = int(subs_text) if subs_text else None
    return (starts + (subs or 0), starts if subs is not None else None, subs)


def _headings_for(table: Tag) -> list[str]:
    """The table's own heading and its ancestors, nearest first."""
    headings: list[str] = []
    seen: set[str] = set()
    level = 7
    for node in table.find_all_previous(["h2", "h3", "h4", "h5"]):
        node_level = int(node.name[1])
        if node_level >= level:
            continue
        level = node_level
        text = node.get_text(" ", strip=True)
        if text not in seen:
            headings.append(text)
            seen.add(text)
        if node_level == 2:
            break
    return headings


def _header_depth(rows: list[Tag]) -> int:
    """How many leading rows are header rows, counting those made entirely of `th`.

    A single header row is assumed when the first row already mixes `th` and `td`, and two is
    the most any observed layout uses; reading further would consume a data row as a header.
    """
    depth = 0
    for row in rows[:2]:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells or any(cell.name != "th" for cell in cells):
            break
        depth += 1
    return max(depth, 1)


def parse_table(table: Tag, headings: list[str]) -> ParsedTable | None:
    """Read one wikitable into entries, or None when its header carries no usable metric.

    `headings` supplies a metric for tables whose columns are bare competition names, and
    excludes the table when it names a squad section.
    """
    if any(SQUAD_HEADING.search(heading) for heading in headings):
        return None

    section_metric: str | None = None
    for heading in headings:
        if APPS_HEADING.search(heading):
            section_metric = "apps"
            break
        if GOALS_HEADING.search(heading):
            section_metric = "goals"
            break

    rows = table.find_all("tr")
    if len(rows) < 2:
        return None

    header_rows = _header_depth(rows)
    mapping, player_column = _resolve_header(_expand(rows[:header_rows]), section_metric)
    if not mapping or player_column is None:
        return None

    metrics = {metric for _, metric in mapping.values()}
    if not metrics & {"apps", "goals"}:
        return None

    entries: list[Entry] = []
    for line in _expand(rows[header_rows:]):
        cell = line.get(player_column)
        if cell is None:
            continue
        identity = _identity(cell)
        if identity is None:
            continue
        key, name = identity
        entry = Entry(player_key=key, player_name=name)
        for column, (competition, metric) in mapping.items():
            target = line.get(column)
            if target is None:
                continue
            parsed = _number(target.get_text(" ", strip=True))
            if parsed is None:
                continue
            value, starts, subs = parsed
            entry.values[(competition, metric)] = value
            if metric == "apps" and starts is not None:
                entry.values[(competition, "starts")] = starts
                entry.values[(competition, "sub_appearances")] = subs or 0
        if entry.values:
            entry.position = _position(line, mapping, player_column)
            entries.append(entry)

    return ParsedTable(entries=entries, metrics=metrics & {"apps", "goals"})


def _position(line: dict[int, Tag], mapping: dict[int, tuple[str, str]], player: int) -> str | None:
    """The position group named in an unmapped cell left of the player column."""
    for column in sorted(line):
        if column >= player or column in mapping:
            continue
        text = line[column].get_text(" ", strip=True).upper()
        if text in POSITION_GROUPS:
            return POSITION_GROUPS[text]
    return None


def reconcile(entries: list[Entry]) -> tuple[list[Entry], list[tuple[Entry, str]]]:
    """Split entries into those whose per-competition figures sum to their own Total, and
    those that disagree, each paired with the metric that failed."""
    kept: list[Entry] = []
    rejected: list[tuple[Entry, str]] = []
    for entry in entries:
        failure: str | None = None
        for metric in ("apps", "goals"):
            declared = entry.values.get(("Total", metric))
            if declared is None:
                continue
            parts = sum(
                value
                for (competition, name), value in entry.values.items()
                if name == metric and competition != "Total"
            )
            if parts != declared:
                failure = metric
                break
        if failure is None:
            kept.append(entry)
        else:
            rejected.append((entry, failure))
    return kept, rejected


def merge(tables: list[ParsedTable]) -> tuple[list[Entry], set[str], list[tuple[Entry, str]]]:
    """Combine one article's tables on the player, returning the merged entries, the metrics
    any table supplied, and entries rejected because two tables disagreed."""
    merged: dict[str, Entry] = {}
    conflicts: list[tuple[Entry, str]] = []
    supplied: set[str] = set()
    for table in tables:
        supplied |= table.metrics
        for entry in table.entries:
            existing = merged.get(entry.player_key)
            if existing is None:
                merged[entry.player_key] = entry
                continue
            for key, value in entry.values.items():
                if key in existing.values and existing.values[key] != value:
                    conflicts.append((entry, f"{key[0]} {key[1]}"))
                    break
                existing.values[key] = value
            existing.position = existing.position or entry.position
    for entry, _ in conflicts:
        merged.pop(entry.player_key, None)
    return list(merged.values()), supplied, conflicts


def league_rows(entries: list[Entry], supplied: set[str]) -> list[dict[str, object]]:
    """One row per player with Premier League appearances, dropping players whose article
    supplied no goals at all rather than reading their absence as zero."""
    rows: list[dict[str, object]] = []
    for entry in entries:
        appearances = entry.values.get((LEAGUE_NAME, "apps"))
        if not appearances:
            continue
        goals = entry.values.get((LEAGUE_NAME, "goals"))
        if goals is None:
            if "goals" not in supplied:
                continue
            goals = 0
        rows.append(
            {
                "player_source_id": entry.player_key,
                "player_name": entry.player_name,
                "position_general": entry.position or "",
                "appearances": appearances,
                "starts": entry.values.get((LEAGUE_NAME, "starts"), ""),
                "sub_appearances": entry.values.get((LEAGUE_NAME, "sub_appearances"), ""),
                "goals": goals,
            }
        )
    return rows


# --------------------------------------------------------------------------- fetching


class Wikipedia:
    """Reads rendered article HTML and link lists from the MediaWiki API."""

    def __init__(self, delay: float = REQUEST_DELAY) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay = delay

    def parse(self, title: str, prop: str = "text") -> dict | None:
        """The API's `parse` result for a title, or None when the article does not exist."""
        response = self.session.get(
            API,
            params={"action": "parse", "page": title, "prop": prop,
                    "redirects": 1, "format": "json"},
            timeout=60,
        )
        time.sleep(self.delay)
        try:
            payload = response.json()
        except ValueError:
            return None
        return None if "error" in payload else payload["parse"]


def club_season_titles(wiki: Wikipedia, season: str) -> list[str]:
    """Club-season article titles for the clubs in that season's league table."""
    parsed = wiki.parse(f"{season} Premier League", prop="text|links")
    if parsed is None:
        return []
    soup = BeautifulSoup(parsed["text"]["*"], "lxml")
    clubs: set[str] = set()
    for table in soup.find_all("table", class_="wikitable"):
        headings = [cell.get_text(" ", strip=True) for cell in table.find_all("th")[:12]]
        if not ({"Team", "Club"} & set(headings) and {"Pld", "Pts"} & set(headings)):
            continue
        for link in table.find_all("a"):
            title = link.get("title")
            if title and "season" not in title.lower():
                clubs.add(title)
        if len(clubs) >= 20:
            break
    pattern = re.compile(rf"^{re.escape(season)} (.+) season$")
    titles = []
    for link in parsed["links"]:
        if link["ns"] != 0 or "exists" not in link:
            continue
        match = pattern.match(link["*"])
        if match and _names_match(match.group(1), clubs):
            titles.append(link["*"])
    return sorted(set(titles))


def _names_match(club: str, clubs: set[str]) -> bool:
    """Whether an article's club name is one of the league table's, allowing for the F.C.
    and A.F.C. suffixes appearing in one and not the other."""
    stem = re.sub(r"\s+(F\.C\.|A\.F\.C\.|FC|AFC)$", "", club).strip()
    for candidate in clubs:
        other = re.sub(r"\s+(F\.C\.|A\.F\.C\.|FC|AFC)$", "", candidate).strip()
        if stem == other:
            return True
    return False


def scrape_article(wiki: Wikipedia, title: str) -> dict:
    """Parse one club-season article into rows, with the counts and revision behind them."""
    parsed = wiki.parse(title)
    if parsed is None:
        return {"title": title, "status": "missing", "rows": [], "rejected": 0}
    soup = BeautifulSoup(parsed["text"]["*"], "lxml")
    tables = []
    for table in soup.find_all("table", class_="wikitable"):
        result = parse_table(table, _headings_for(table))
        if result is not None and result.entries:
            tables.append(result)
    if not tables:
        return {"title": title, "revid": parsed.get("revid"),
                "status": "no table", "rows": [], "rejected": 0}

    checked: list[Entry] = []
    rejected = 0
    for table in tables:
        kept, bad = reconcile(table.entries)
        table.entries = kept
        rejected += len(bad)
        checked.extend(kept)

    entries, supplied, conflicts = merge(tables)
    rejected += len(conflicts)
    rows = league_rows(entries, supplied)
    return {
        "title": title,
        "revid": parsed.get("revid"),
        "status": "ok" if rows else "no rows",
        "rows": rows,
        "rejected": rejected,
    }


# --------------------------------------------------------------------------- command line


FIELDNAMES = (
    "provider", "player_source_id", "player_name", "club_name",
    "competition_name", "season_name", "position_general",
    "appearances", "starts", "sub_appearances", "goals",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", nargs="*", default=list(SEASONS))
    parser.add_argument("--out", type=Path, default=Path("data/player_seasons.csv"))
    parser.add_argument("--sources", type=Path, default=Path("data/sources.json"))
    parser.add_argument("--min-parse-rate", type=float, default=0.80)
    parser.add_argument("--min-reconcile-rate", type=float, default=0.95)
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY)
    args = parser.parse_args()

    wiki = Wikipedia(delay=args.delay)
    rows: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    discovered = parsed_ok = kept = rejected = 0

    for season in args.seasons:
        titles = club_season_titles(wiki, season)
        print(f"{season}: {len(titles)} club-season articles", file=sys.stderr)
        for title in titles:
            discovered += 1
            result = scrape_article(wiki, title)
            club = title[len(season) + 1: -len(" season")]
            for row in result["rows"]:
                row.update(
                    provider="wikipedia",
                    club_name=club,
                    competition_name=LEAGUE_NAME,
                    season_name=season.replace("–", "/")[:5] + season[-2:],
                )
                rows.append(row)
            kept += len(result["rows"])
            rejected += result["rejected"]
            if result["status"] == "ok":
                parsed_ok += 1
            sources.append(
                {
                    "title": title,
                    "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                    "revid": result.get("revid"),
                    "status": result["status"],
                    "rows": len(result["rows"]),
                    "rejected": result["rejected"],
                }
            )
            print(f"  {club:<34} {result['status']:<9} rows={len(result['rows']):<3}"
                  f" rejected={result['rejected']}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["season_name"], r["club_name"], r["player_name"])):
            writer.writerow(row)

    parse_rate = parsed_ok / discovered if discovered else 0.0
    reconcile_rate = kept / (kept + rejected) if kept + rejected else 0.0
    args.sources.write_text(
        json.dumps(
            {
                "layout_version": LAYOUT_VERSION,
                "retrieved": date.today().isoformat(),
                "licence": "CC BY-SA 4.0",
                "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "seasons": list(args.seasons),
                "articles_discovered": discovered,
                "articles_parsed": parsed_ok,
                "rows": kept,
                "rows_rejected": rejected,
                "articles": sources,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\n{kept} rows from {parsed_ok}/{discovered} articles; "
          f"{rejected} rejected ({reconcile_rate:.1%} kept)", file=sys.stderr)

    if parse_rate < args.min_parse_rate or reconcile_rate < args.min_reconcile_rate:
        failed = [s["title"] for s in sources if s["status"] != "ok"]
        print(
            f"\nLayout check failed: parsed {parse_rate:.1%} of articles "
            f"(floor {args.min_parse_rate:.0%}), reconciled {reconcile_rate:.1%} of rows "
            f"(floor {args.min_reconcile_rate:.0%}). Wikipedia's table layout has probably "
            f"changed since LAYOUT_VERSION {LAYOUT_VERSION}.\nFailed: " + ", ".join(failed),
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
