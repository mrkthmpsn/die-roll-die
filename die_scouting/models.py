from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

Model = Literal["beta_binomial", "gamma_exponential", "gamma_poisson", "normal_normal"]

POSTERIOR_PARAM_NAMES: dict[Model, tuple[str, str]] = {
    "beta_binomial": ("alpha", "beta"),
    "gamma_exponential": ("alpha", "beta"),
    "gamma_poisson": ("alpha", "beta"),
    "normal_normal": ("mu", "sigma"),
}
"""The names of the two parameters each model carries, in the order
`PosteriorSampler.posterior_params` returns them.

What the pair counts follows the model:

| model | first | second |
| --- | --- | --- |
| `beta_binomial` | `alpha`, successes | `beta`, failures |
| `gamma_exponential` | `alpha`, events | `beta`, the time they took |
| `gamma_poisson` | `alpha`, events | `beta`, the exposure they occurred in |
| `normal_normal` | `mu`, the estimated mean | `sigma`, how uncertain that mean is |

Three models name their pair `alpha` and `beta`, after the gamma and beta distributions
those parameters belong to: `alpha / beta` is a rate of events per unit of time for both
gamma models, and `alpha / (alpha + beta)` is a proportion for `beta_binomial`. A
`normal_normal` prior carries a third parameter, `sigma_obs`, holding the spread of
individual observations.
"""


class Record(BaseModel):
    """Representation of a single entity's single value, and the denominator it was
    measured against.

    What the pair means follows the model a prior is fitted or updated under:

    | model | `value` | `denominator` |
    | --- | --- | --- |
    | `gamma_poisson` | count of events | exposure they occurred in |
    | `gamma_exponential` | amount of time | count of events filling it |
    | `beta_binomial` | count of successes | count of attempts |
    | `normal_normal` | measured quantity | weight it carries |

    Twelve goals across thirty appearances is `value=12.0, denominator=30.0` under
    `gamma_poisson`. The `gamma_exponential` row inverts the others deliberately: it holds
    the same two quantities as `gamma_poisson`, an amount of time and a number of events,
    but in the opposite fields, because `gamma_poisson` fixes the time and counts the
    events while `gamma_exponential` fixes the events and measures the time. A denominator
    of `1.0` states that the value stands on its own.

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

    `params` holds the model's parameters by name, `POSTERIOR_PARAM_NAMES` giving the two
    every model carries and what each of them counts; a `normal_normal` prior carries
    `sigma_obs` besides.
    """

    stat_id: str
    entity_type: str
    scope: dict[str, str] = {}
    model: Model
    params: dict[str, float]

    @property
    def ordered_params(self) -> tuple[float, float]:
        """The two values `POSTERIOR_PARAM_NAMES` names for this model, in that order."""
        first, second = POSTERIOR_PARAM_NAMES[self.model]
        return self.params[first], self.params[second]


class Face(BaseModel):
    """One face of the weighted die: a bin of the quality distribution."""

    label: str
    weight: float
    value_range: tuple[float, float]


class DieMetadata(BaseModel):
    """What a die was built from: which entity and stat, the scope and prior behind it, the
    entity's own record, and how the faces were binned.

    Every field is optional, a die over arbitrary samples carrying none of them. `strategy`
    and `draws` are set by `assemble_die_from_samples`; `extra` holds anything a caller needs
    that this model does not name.

    `observed_value` and `observed_denominator` are sums over the entity's observations and
    `observed_periods` counts them, so a record spanning two periods can be told from one
    spanning nine.
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
    observed_periods: int | None = None
    predicted_denominator: float | None = None
    denominator_unit: str | None = None
    strategy: Literal["equal_weight", "equal_width"] | None = None
    draws: int | None = None
    extra: dict[str, Any] = {}


class Die(BaseModel):
    """Basic representation of a die."""

    faces: list[Face]
    metadata: DieMetadata = DieMetadata()
