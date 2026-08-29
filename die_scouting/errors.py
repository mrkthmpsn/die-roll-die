from __future__ import annotations


class PriorFitError(ValueError):
    """Raised when observations cannot produce a prior of the model asked for."""


class InsufficientData(PriorFitError):
    """Raised when the observations are the right shape but there are too few of them."""


class UnsuitableModel(PriorFitError):
    """Raised when the observations contradict the model asked for."""


class SamplingError(ValueError):
    """Raised when a sampler cannot draw from the prior and observations it was given."""


class EntityTypeMismatch(SamplingError):
    """Raised when an entity's observations and the prior describe different entity types."""


class MissingPriorParam(SamplingError):
    """Raised when a prior's params lack a key the model it names needs."""


class UnsuitableDenominator(SamplingError):
    """Raised when a denominator cannot be sampled over: a predicted denominator that is
    negative, or fractional where the model counts it; or an observation's denominator that
    is not positive.
    """


class InsufficientObservations(SamplingError):
    """Raised when an entity has too few observations to resample."""
