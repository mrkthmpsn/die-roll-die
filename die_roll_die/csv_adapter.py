from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from .models import Record


class ColumnMap(BaseModel):
    """Which of a CSV's columns fill each role a `CsvDataAdapter` needs.

    Only these roles are mapped, and most of a file's columns will fill none of them:

    - `entity` identifies which entity a row belongs to, and is repeated across that
      entity's rows. It becomes `Record.entity_id`.
    - `entity_type` says what that identifier names — "player", "club" — and is a constant
      for the file rather than one of its columns, a CSV being at one grain. It becomes
      `Record.entity_type`, and keeps priors for one kind of entity from being stored over
      another's.
    - `denominator` holds what the row's value was measured against — appearances,
      nineties, attempts. It becomes `Record.denominator`.
    - `name` is a human-readable label for an entity, used by `entity_ids_for_name` to
      search and `entity_name` to resolve. It is a fact about the entity rather than about
      one of its observations, so it is never copied onto a `Record`. Optional, a dataset
      being allowed to have only ids.
    - `dimensions` names the columns along which separate priors might be fitted, and each
      becomes an entry in `Record.dimensions`.

    The column holding the stat is not mapped, being chosen per call as `stat_id`; nor are
    the columns a `scope` filters on, which are checked against the file's header when the
    scope is used. Filtering therefore works on any column of the file, while `scopes_for`
    can only enumerate a mapped dimension.
    """

    entity: str
    entity_type: str
    denominator: str
    name: str | None = None
    dimensions: tuple[str, ...] = ()


class CsvDataAdapter:
    """Reads Records from a CSV, one row per entity per period.

    A column of that file is used in one of three ways. It is mapped to a role by
    `columns`; or named per call as `stat_id`, which must be one of `numeric_columns` and
    is read into `Record.value`; or named in a `scope`, filtering rows by exact string
    match, which may be any column of the file whether mapped or not.

    Rows whose denominator is zero, blank or unparseable are dropped when the file is read,
    as are rows whose `stat_id` column is blank when records are requested.

    Raises:
        ValueError: if any column named by `columns` is not in the file.
    """

    def __init__(self, path: str | Path, columns: ColumnMap) -> None:
        self.path = Path(path)
        self.column_map = columns

        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.columns: tuple[str, ...] = tuple(reader.fieldnames or ())
            rows = list(reader)

        mapped = {"entity": columns.entity, "denominator": columns.denominator}
        if columns.name is not None:
            mapped["name"] = columns.name
        for index, column in enumerate(columns.dimensions):
            mapped[f"dimensions[{index}]"] = column
        for role, column in mapped.items():
            if column not in self.columns:
                raise ValueError(
                    f"{role} column {column!r} is not in the file; "
                    f"columns are {', '.join(self.columns)}"
                )

        self._rows = []
        for row in rows:
            denominator = _as_float(row[columns.denominator])
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
        """Entity ids whose name column contains `name`, matched case-insensitively.

        Raises:
            ValueError: if the column map named no `name` column.
        """
        needle = self._name_column()
        return sorted({
            row[self.column_map.entity]
            for row in self._rows
            if name.casefold() in row[needle].casefold()
        })

    def entity_name(self, entity_id: str) -> str | None:
        """The label held for `entity_id`, or None where the file has no row for it.

        Raises:
            ValueError: if the column map named no `name` column.
        """
        column = self._name_column()
        for row in self._rows:
            if row[self.column_map.entity] == entity_id:
                return row[column]
        return None

    def _name_column(self) -> str:
        if self.column_map.name is None:
            raise ValueError("this adapter's ColumnMap names no `name` column")
        return self.column_map.name

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

        entity_column = self.column_map.entity
        records = []
        for row in self._rows:
            if entity_id is not None and row[entity_column] != entity_id:
                continue
            if any(row[key] != value for key, value in scope.items()):
                continue
            value = _as_float(row[stat_id])
            if value is None:
                continue
            records.append(
                Record(
                    entity_id=row[entity_column],
                    entity_type=self.column_map.entity_type,
                    value=value,
                    denominator=float(row[self.column_map.denominator]),
                    dimensions={
                        column: row[column] for column in self.column_map.dimensions
                    },
                )
            )
        return records


def _as_float(value: str | None) -> float | None:
    """Return `value` as a float, or None where it is blank or unparseable."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
