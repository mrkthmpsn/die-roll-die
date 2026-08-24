from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Record(BaseModel):
    """Representation of a single entity's single value, and the denominator it was
    measured against.

    What the pair means follows the prior family it is fitted or updated under: a count
    over the opportunity it accumulated in, as twelve goals across thirty nineties
    (`value=12.0, denominator=30.0`); successes over attempts, as thirty headers from a
    hundred shots; or a measurement over the weight it carries, where `value / denominator`
    is the measured quantity per unit. A denominator of `1.0` states that the value stands
    on its own.
    """

    entity_id: str
    value: float
    denominator: float
    context: dict[str, Any] = {}


class PriorParams(BaseModel):
    """Fitted prior distribution parameters for a stat, within an optional scope.

    `scope` is a set of optional, composable filter dimensions (e.g. position group,
    competition); an empty dict means the global, unscoped prior for this stat.

    `params` holds the family's parameters by name: `alpha` and `beta` for gamma, where
    `beta` is a rate in units of 1/denominator.
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
