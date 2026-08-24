from __future__ import annotations


class PriorFitError(ValueError):
    """Raised when observations cannot produce a prior of the family asked for."""


class InsufficientData(PriorFitError):
    """Raised when the observations are the right shape but there are too few of them."""


class UnsuitableFamily(PriorFitError):
    """Raised when the observations contradict the family asked for."""
