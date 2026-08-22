from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Record(BaseModel):
    """Representation of a single entity's single value, and the exposure it accumulated
    over.

    `value` is a count or measurement and `exposure` its denominator; twelve goals across
    thirty nineties is `value=12.0, exposure=30.0`. An exposure of `1.0` states that the
    value stands on its own.
    """

    entity_id: str
    value: float
    exposure: float
    context: dict[str, Any] = {}


class PriorParams(BaseModel):
    """Fitted prior distribution parameters for a stat, within an optional scope.

    `scope` is a set of optional, composable filter dimensions (e.g. position group,
    competition); an empty dict means the global, unscoped prior for this stat.

    `params` holds the family's parameters by name: `alpha` and `beta` for gamma, where
    `beta` is a rate in units of 1/exposure.
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
    """Basic representation of a die."""

    faces: list[Face]
    metadata: dict[str, Any] = {}
