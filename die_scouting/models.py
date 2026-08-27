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

    `entity_type` says what kind of thing `entity_id` names, so a player's observations and
    a club's cannot be mistaken for one another downstream.

    `dimensions` holds the values of the columns priors might be fitted along — a position
    group, a season. It exists because a Record outlives the source it came from: whatever
    produced it can inspect its own file or API, and nothing downstream can, so `scopes_for`
    has only this to enumerate.
    """

    entity_id: str
    entity_type: str
    value: float
    denominator: float
    dimensions: dict[str, str] = {}


class PriorParams(BaseModel):
    """Fitted prior distribution parameters for a stat, for one kind of entity, within an
    optional scope.

    `scope` is a set of optional, composable filter dimensions (e.g. position group,
    competition); an empty dict means the global, unscoped prior for this stat.

    `params` holds the family's parameters by name: `alpha` and `beta` for gamma, where
    `beta` is a rate in units of 1/denominator.
    """

    stat_id: str
    entity_type: str
    scope: dict[str, str] = {}
    family: Literal["beta", "gamma", "normal"]
    params: dict[str, float]


class Face(BaseModel):
    """One face of the weighted die: a bin of the quality distribution."""

    label: str
    weight: float
    value_range: tuple[float, float]


class DieMetadata(BaseModel):
    """What a die was built from: which entity and stat, the scope and prior behind it, the
    entity's own record, and how the faces were binned.

    Every field is optional, a die over arbitrary samples carrying none of them. `strategy`
    and `draws` are set by `build_die`; `extra` holds anything a caller needs that this
    model does not name.
    """

    entity_id: str | None = None
    entity_type: str | None = None
    entity_name: str | None = None
    stat_id: str | None = None
    scope: dict[str, str] = {}
    prior: PriorParams | None = None
    posterior_params: dict[str, float] = {}
    observed_value: float | None = None
    observed_denominator: float | None = None
    predicted_denominator: float | None = None
    denominator_unit: str | None = None
    strategy: Literal["equal_weight", "equal_width"] | None = None
    draws: int | None = None
    extra: dict[str, Any] = {}


class Die(BaseModel):
    """Basic representation of a die."""

    faces: list[Face]
    metadata: DieMetadata = DieMetadata()
