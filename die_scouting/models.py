from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Record(BaseModel):
    """A single observation: one match's value for one stat, for one entity."""

    entity_id: str
    value: float
    context: dict[str, Any] = {}


class PriorParams(BaseModel):
    """Fitted prior distribution parameters for a stat, within an optional scope.

    `scope` is a set of optional, composable filter dimensions (e.g. position group,
    competition). An empty dict means the global, unscoped prior for this stat.
    """

    stat_id: str
    scope: dict[str, str] = {}
    family: Literal["beta", "gamma", "normal"]
    params: dict[str, float]


class Face(BaseModel):
    """One face of the weighted die: a bin of the quality distribution."""

    label: str
    weight: float
    value_range: tuple[float, float]


class Die(BaseModel):
    """The contract handed to a frontend roller. No stats knowledge required to consume it."""

    faces: list[Face]
    metadata: dict[str, Any] = {}
