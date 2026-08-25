from __future__ import annotations

import csv
from pathlib import Path

from .models import Record

ENTITY_COLUMN = "player_source_id"
CONTEXT_COLUMNS = ("player_name", "season_name", "position", "position_general")


class CsvDataAdapter:
    """Reads Records from a player-season CSV, one row per entity per season.

    `stat_id` names the column read into `Record.value` and must be one of
    `numeric_columns`; `denominator_column` names the column read into `Record.denominator`.
    A `scope` filters rows by exact string match, keyed by column name.

    Rows whose denominator is zero, blank or unparseable are dropped when the file is read,
    as are rows whose `stat_id` column is blank when records are requested.

    Raises:
        ValueError: if `denominator_column` is not a column of the file.
    """

    def __init__(self, path: str | Path, denominator_column: str = "appearances") -> None:
        self.path = Path(path)
        self.denominator_column = denominator_column

        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.columns: tuple[str, ...] = tuple(reader.fieldnames or ())
            rows = list(reader)

        if denominator_column not in self.columns:
            raise ValueError(
                f"denominator column {denominator_column!r} is not in the file; "
                f"columns are {', '.join(self.columns)}"
            )

        self._rows = []
        for row in rows:
            denominator = _as_float(row[denominator_column])
            if denominator is not None and denominator > 0:
                self._rows.append(row)

        self.numeric_columns: tuple[str, ...] = tuple(
            column
            for column in self.columns
            if any(_as_float(row[column]) is not None for row in self._rows)
        )

    def get_entity_observations(
        self, entity_id: str, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-observation values for a single entity."""
        return self._records(stat_id, scope, entity_id=entity_id)

    def get_population_observations(
        self, stat_id: str, scope: dict[str, str] | None = None
    ) -> list[Record]:
        """Per-observation values for every entity matching `scope`."""
        return self._records(stat_id, scope)

    def entity_ids_for_name(self, name: str) -> list[str]:
        """Entity ids whose `player_name` contains `name`, matched case-insensitively."""
        needle = name.casefold()
        return sorted({
            row[ENTITY_COLUMN] for row in self._rows if needle in row["player_name"].casefold()
        })

    def _records(
        self, stat_id: str, scope: dict[str, str] | None, entity_id: str | None = None
    ) -> list[Record]:
        if stat_id not in self.numeric_columns:
            raise ValueError(
                f"stat {stat_id!r} is not a numeric column of the file; "
                f"numeric columns are {', '.join(self.numeric_columns)}"
            )
        scope = scope or {}
        for key in scope:
            if key not in self.columns:
                raise ValueError(
                    f"scope key {key!r} is not a column of the file; "
                    f"columns are {', '.join(self.columns)}"
                )

        records = []
        for row in self._rows:
            if entity_id is not None and row[ENTITY_COLUMN] != entity_id:
                continue
            if any(row[key] != value for key, value in scope.items()):
                continue
            value = _as_float(row[stat_id])
            if value is None:
                continue
            records.append(
                Record(
                    entity_id=row[ENTITY_COLUMN],
                    value=value,
                    denominator=float(row[self.denominator_column]),
                    context={column: row[column] for column in CONTEXT_COLUMNS if column in row},
                )
            )
        return records


def _as_float(value: str | None) -> float | None:
    """Return `value` as a float, or None where it is blank or unparseable."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
