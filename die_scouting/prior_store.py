from __future__ import annotations

from typing import Protocol

from .models import PriorParams


class PriorStore(Protocol):
    """Persists discovered priors, keyed by (stat_id, scope)."""

    def save(self, params: PriorParams) -> None: ...

    def get(self, stat_id: str, scope: dict[str, str]) -> PriorParams | None:
        """Return the prior stored for exactly this `stat_id` and `scope`, or None."""
        ...


def resolve_prior(store: PriorStore, stat_id: str, scope: dict[str, str]) -> PriorParams:
    """Look up the prior for `stat_id` whose scope most closely matches `scope`, falling
    back to broader scopes and finally the unscoped prior.

    Raises:
        LookupError: if no prior exists for this stat at any scope.
    """
    raise NotImplementedError
